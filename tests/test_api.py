import pytest
from fastapi.testclient import TestClient

from askdocs.api.main import create_app


@pytest.fixture
def client(make_services, tmp_path):
    services = make_services(ingest_root=tmp_path, max_upload_mb=1, warmup_models=False)
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


def parse_sse(text: str) -> list[tuple[str, dict]]:
    import json

    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_ask_returns_cited_answer(client):
    r = client.post("/api/v1/ask", json={"question": "How many weeks of parental leave?", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["query_id"].startswith("q_") and not body["abstained"]
    cite = body["citations"][0]
    assert (cite["n"], cite["doc_id"], cite["file_name"], cite["page"]) == (1, "leave", "leave.md", None)
    assert cite["section_path"] == ["Leave"] and "20 weeks" in cite["snippet"]
    assert body["usage"]["input_tokens"] == 100
    assert {"retrieve", "rerank", "generate", "total"} <= body["latency_ms"].keys()


def test_ask_validation_errors(client):
    def err(payload):
        r = client.post("/api/v1/ask", json=payload)
        return r.status_code, r.json()["error"]["code"], r.json()["error"]["message"]

    status, code, message = err({"question": "   "})
    assert (status, code) == (400, "invalid_request") and "empty" in message
    assert err({"question": "x", "top_k": 50})[:2] == (400, "invalid_request")
    status, _, message = err({"question": "x", "filters": {"doc_ids": ["nope"]}})
    assert status == 400 and "nope" in message


def test_ask_with_filter(client):
    r = client.post("/api/v1/ask", json={"question": "laptops reported", "filters": {"doc_ids": ["it"]}})
    assert r.status_code == 200


@pytest.mark.parametrize(
    "error, status, code",
    [
        ("LLMRateLimited", 429, "rate_limited"),
        ("LLMTimeout", 504, "timeout"),
        ("LLMNotConfigured", 500, "internal_error"),
        ("LLMRefusal", 422, "refused"),
    ],
)
def test_llm_errors_map_to_status(client, monkeypatch, error, status, code):
    from askdocs.generate import llm as llm_module

    def fail(*a, **k):
        raise getattr(llm_module, error)("upstream problem")

    monkeypatch.setattr(client.services.llm, "complete", fail)
    r = client.post("/api/v1/ask", json={"question": "parental leave weeks"})
    assert (r.status_code, r.json()["error"]["code"]) == (status, code)


def test_unexpected_error_hides_details(client, monkeypatch):
    monkeypatch.setattr(client.services.llm, "complete", lambda *a: 1 / 0)
    r = client.post("/api/v1/ask", json={"question": "parental leave weeks"})
    assert r.status_code == 500 and r.json()["error"]["message"] == "Unexpected server error."


def test_ask_stream_sse(client):
    r = client.post("/api/v1/ask/stream", json={"question": "parental leave weeks"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert events[0][0] == "meta" and events[-1][0] == "done"
    assert "".join(d["text"] for e, d in events if e == "token") == events[-1][1]["answer"]


def test_ask_stream_error_event(client, monkeypatch):
    from askdocs.generate.llm import LLMTimeout

    def fail(*a, **k):
        raise LLMTimeout("slow")
        yield  # pragma: no cover

    monkeypatch.setattr(client.services.llm, "stream", fail)
    events = parse_sse(client.post("/api/v1/ask/stream", json={"question": "parental leave weeks"}).text)
    assert events[-1][0] == "error" and events[-1][1]["code"] == "timeout" and events[-1][1]["status"] == 504
    r = client.post("/api/v1/ask/stream", json={"question": ""})
    assert r.status_code == 400


def test_feedback_is_stored_with_the_trace(client):
    from askdocs.store.models import Feedback

    answer = client.post("/api/v1/ask", json={"question": "parental leave weeks"}).json()
    r = client.post("/api/v1/feedback", json={"query_id": answer["query_id"], "rating": "helpful"})
    assert r.status_code == 201 and r.json()["rating"] == "helpful"
    r = client.post(
        "/api/v1/feedback", json={"query_id": answer["query_id"], "rating": "not_helpful", "comment": "too short"}
    )
    assert r.status_code == 201

    with client.services.db.session() as s:
        [row] = s.query(Feedback).all()
    assert (row.rating, row.comment, row.question) == ("not_helpful", "too short", "parental leave weeks")
    assert row.cited_chunk_ids == [c["chunk_id"] for c in answer["citations"]]


def test_feedback_errors(client):
    r = client.post("/api/v1/feedback", json={"query_id": "q_nope", "rating": "helpful"})
    assert (r.status_code, r.json()["error"]["code"]) == (404, "not_found")
    r = client.post("/api/v1/feedback", json={"query_id": "q_x", "rating": "meh"})
    assert r.status_code == 400


def test_warm_up_loads_models_and_survives_failures(make_services, caplog):
    from askdocs.api.main import warm_up

    services = make_services()
    warm_up(services)  # fake embedder and reranker: just must not raise
    services.__dict__["reranker"] = None  # broken reranker
    warm_up(services)
    assert "warm-up failed" in caplog.text
