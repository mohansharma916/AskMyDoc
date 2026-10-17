import pytest
from fastapi.testclient import TestClient

from askdocs.api.main import create_app


@pytest.fixture
def client(make_services, tmp_path):
    services = make_services(ingest_root=tmp_path, max_upload_mb=1)
    app = create_app(services)
    with TestClient(app, raise_server_exceptions=False) as c:
        c.services = services
        c.jobs = app.state.jobs
        yield c


def test_health(client):
    body = client.get("/api/v1/health").json()
    assert body["database"] and body["qdrant"]
    assert body["documents"] == 2 and body["chunks"] == 3
    assert body["llm"]["provider"] == "anthropic"


def test_upload_ingest_job_and_documents(client):
    r = client.post("/api/v1/ingest", files=[("files", ("travel.md", b"# Travel\n\nBook economy.", "text/markdown"))])
    assert r.status_code == 202
    job = r.json()
    assert job["status"] in ("queued", "running", "completed") and job["files"] == 1
    client.jobs.wait()
    done = client.get(f"/api/v1/ingest/{job['job_id']}").json()
    assert done["status"] == "completed"
    assert done["counts"] == {"indexed": 1, "updated": 0, "unchanged": 0, "failed": 0, "chunks": 1}

    docs = client.get("/api/v1/documents").json()["documents"]
    assert [d["doc_id"] for d in docs] == ["it", "leave", "travel"]
    assert docs[1]["chunks"] == 2 and docs[1]["title"] == "Leave"


def test_ingest_path_under_root(client, tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.txt").write_text("Alpha policy text.")
    (tmp_path / "docs" / "skip.png").write_bytes(b"x")
    job = client.post("/api/v1/ingest", data={"path": "docs"}).json()
    client.jobs.wait()
    assert client.get(f"/api/v1/ingest/{job['job_id']}").json()["counts"]["indexed"] == 1


def test_ingest_errors(client):
    def err(r):
        return r.status_code, r.json()["error"]["code"]

    assert err(client.post("/api/v1/ingest")) == (400, "invalid_request")
    assert err(client.post("/api/v1/ingest", data={"path": "/etc"})) == (400, "invalid_request")
    assert err(client.post("/api/v1/ingest", data={"path": "missing"})) == (404, "not_found")
    big = ("files", ("big.txt", b"x" * (2**20 + 1), "text/plain"))
    assert err(client.post("/api/v1/ingest", files=[big])) == (413, "file_too_large")
    assert err(client.get("/api/v1/ingest/j_nope")) == (404, "not_found")


def test_failed_job(client, monkeypatch):
    def boom(files):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(client.services.indexer, "ingest_files", boom)
    job = client.post("/api/v1/ingest", files=[("files", ("a.txt", b"x", "text/plain"))]).json()
    client.jobs.wait()
    done = client.get(f"/api/v1/ingest/{job['job_id']}").json()
    assert done["status"] == "failed" and done["error"] == "qdrant down"


def test_delete_document(client):
    assert client.delete("/api/v1/documents/it").status_code == 204
    r = client.delete("/api/v1/documents/it")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert "trace_id" in r.json()["error"]


def test_openapi_docs(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/v1/health", "/api/v1/ingest", "/api/v1/documents"} <= paths.keys()
