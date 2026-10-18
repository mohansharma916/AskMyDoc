from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from askdocs.api.main import create_app
from askdocs.store.models import BrowserSession, Chunk, Document, Trace

from .conftest import FakeLLM


@pytest.fixture
def app_client(make_services, tmp_path):
    llm = FakeLLM("The vault code is 4417 [1].")
    services = make_services(llm=llm, ingest_root=tmp_path, warmup_models=False)
    app = create_app(services)
    with TestClient(app, raise_server_exceptions=False) as c:
        c.services, c.jobs, c.llm = services, app.state.jobs, llm
        yield c


def new_session(client) -> dict:
    return {"X-Session-Id": client.post("/api/v1/sessions").json()["session_id"]}


def upload(client, headers, name="secret.md", data=b"# Vault\n\nThe vault code is 4417.") -> str:
    job = client.post("/api/v1/ingest", headers=headers, files=[("files", (name, data, "text/markdown"))]).json()
    client.jobs.wait()
    return client.get(f"/api/v1/ingest/{job['job_id']}", headers=headers).json()["results"][0]["doc_id"]


def doc_ids(client, headers=None) -> list[str]:
    return [d["doc_id"] for d in client.get("/api/v1/documents", headers=headers or {}).json()["documents"]]


def age(client, headers, seconds=3600) -> None:
    with client.services.db.session() as s:
        row = s.get(BrowserSession, headers["X-Session-Id"])
        row.last_seen_at = datetime.now(UTC) - timedelta(seconds=seconds)


def test_uploads_are_private_to_their_session(app_client):
    a, b = new_session(app_client), new_session(app_client)
    doc = upload(app_client, a)

    assert doc in doc_ids(app_client, a)
    assert doc not in doc_ids(app_client, b) and doc not in doc_ids(app_client)  # other browser, or none
    assert {"it", "leave"} <= set(doc_ids(app_client, b))  # shared documents stay visible to everyone
    assert app_client.get(f"/api/v1/documents/{doc}", headers=b).status_code == 404
    assert app_client.get(f"/api/v1/documents/{doc}/file", headers=b).status_code == 404
    assert app_client.delete(f"/api/v1/documents/{doc}", headers=b).status_code == 404
    assert app_client.get("/api/v1/health", headers=b).json()["documents"] == 2
    assert app_client.get("/api/v1/health", headers=a).json()["documents"] == 3

    app_client.post("/api/v1/ask", headers=b, json={"question": "What is the vault code?"})
    app_client.post("/api/v1/ask", headers=a, json={"question": "What is the vault code?"})
    prompts = [call[0]["content"] for call in app_client.llm.calls]
    assert all("4417" not in p for p in prompts[:-1]) and "4417" in prompts[-1]

    r = app_client.post("/api/v1/ask", headers=b, json={"question": "vault", "filters": {"doc_ids": [doc]}})
    assert r.status_code == 400  # can't target another session's document either


def test_same_file_name_in_two_sessions_does_not_collide(app_client):
    a, b = new_session(app_client), new_session(app_client)
    doc_a = upload(app_client, a, "report.md", b"# Report\n\nRevenue grew 10 percent.")
    doc_b = upload(app_client, b, "report.md", b"# Report\n\nRevenue fell 3 percent.")
    assert doc_a != doc_b
    text = lambda h, d: app_client.get(f"/api/v1/documents/{d}", headers=h).json()["full_text"]  # noqa: E731
    assert "grew 10" in text(a, doc_a) and "fell 3" in text(b, doc_b)


def test_expired_session_deletes_documents_vectors_files_and_traces(app_client):
    a, b = new_session(app_client), new_session(app_client)
    doc = upload(app_client, a)
    upload(app_client, b, "keep.md", b"# Keep\n\nThis belongs to session B.")
    query_id = app_client.post("/api/v1/ask", headers=a, json={"question": "What is the vault code?"}).json()[
        "query_id"
    ]
    assert app_client.post("/api/v1/feedback", headers=a, json={"query_id": query_id, "rating": "helpful"}).is_success
    svc = app_client.services
    upload_dir = svc.sessions.upload_dir(a["X-Session-Id"])
    points_before = svc.vectors.count()
    assert (upload_dir / "secret.md").is_file()

    age(app_client, a)
    assert svc.sessions.sweep() == [a["X-Session-Id"]]

    with svc.db.session() as s:
        assert s.get(Document, doc) is None
        assert s.scalar(select(func.count()).select_from(Chunk).where(Chunk.doc_id == doc)) == 0
        assert s.get(Trace, query_id) is None
        assert s.get(BrowserSession, a["X-Session-Id"]) is None
    assert svc.vectors.count() == points_before - 1
    assert not svc.bm25.search("vault code 4417")
    assert not upload_dir.exists()
    assert "keep" in "".join(doc_ids(app_client, b))  # other sessions are untouched

    r = app_client.get("/api/v1/documents", headers=a)
    assert r.status_code == 410 and r.json()["error"]["code"] == "session_expired"


def test_expiry_is_enforced_on_the_next_request_before_the_sweep(app_client):
    a = new_session(app_client)
    doc = upload(app_client, a)
    age(app_client, a)
    assert app_client.post("/api/v1/ask", headers=a, json={"question": "vault"}).status_code == 410
    with app_client.services.db.session() as s:
        assert s.get(Document, doc) is None


def test_heartbeat_extends_and_status_check_does_not(app_client):
    a = new_session(app_client)
    age(app_client, a, seconds=200)
    before = app_client.get("/api/v1/sessions/current", headers=a).json()
    assert before["ttl_s"] == 300
    remaining = datetime.fromisoformat(before["expires_at"]) - datetime.now(UTC)
    assert remaining < timedelta(seconds=101)  # GET did not count as activity

    assert 0 < before["expires_in_s"] < 101
    after = app_client.post("/api/v1/sessions/current/heartbeat", headers=a).json()
    assert after["expires_in_s"] > 290
    remaining = datetime.fromisoformat(after["expires_at"]) - datetime.now(UTC)
    assert remaining > timedelta(seconds=290)


def test_sweep_spares_sessions_with_a_running_ingest(app_client):
    a = new_session(app_client)
    doc = upload(app_client, a)
    age(app_client, a)
    assert app_client.services.sessions.sweep(keep={a["X-Session-Id"]}) == []
    with app_client.services.db.session() as s:
        assert s.get(Document, doc) is not None


def test_end_session_deletes_everything_now(app_client):
    a = new_session(app_client)
    doc = upload(app_client, a)
    assert app_client.delete("/api/v1/sessions/current", headers=a).status_code == 204
    with app_client.services.db.session() as s:
        assert s.get(Document, doc) is None
    assert app_client.get("/api/v1/sessions/current", headers=a).status_code == 410


def test_upload_requires_a_session_and_strips_directories_from_names(app_client):
    r = app_client.post("/api/v1/ingest", files=[("files", ("a.txt", b"x", "text/plain"))])
    assert r.status_code == 400 and r.json()["error"]["code"] == "session_required"

    a = new_session(app_client)
    upload(app_client, a, "../../evil.md", b"# Evil\n\nShould stay inside the session folder.")
    assert (app_client.services.sessions.upload_dir(a["X-Session-Id"]) / "evil.md").is_file()
    assert not (app_client.services.settings.ingest_root.parent / "evil.md").exists()
