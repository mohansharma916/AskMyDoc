import uuid

import pytest

from askdocs.retrieve.vector import QdrantIndex, VectorPoint, make_client


@pytest.fixture
def index(embedder):
    return QdrantIndex(make_client(":memory:"), "test", embedder.dim)


def _point(embedder, doc_id, text):
    return VectorPoint(str(uuid.uuid4()), embedder.embed_query(text), {"doc_id": doc_id, "text": text})


def test_upsert_count_and_delete_by_document(index, embedder):
    index.upsert([_point(embedder, "a", "leave"), _point(embedder, "a", "pto"), _point(embedder, "b", "x")])
    assert index.count() == 3
    index.delete_document("a")
    assert index.count() == 1
    index.delete_document("missing")  # no-op
    assert index.count() == 1


def test_upsert_batches(index, embedder, monkeypatch):
    monkeypatch.setattr("askdocs.retrieve.vector.BATCH_SIZE", 2)
    index.upsert([_point(embedder, "a", f"t{i}") for i in range(5)])
    assert index.count() == 5


def test_ping_and_client_modes(index, tmp_path):
    assert index.ping()
    assert make_client(str(tmp_path / "qdrant")).get_collections() is not None


def test_search_returns_candidates_with_payload_and_filters(index, embedder):
    hr = {"doc_id": "hr", "text": "leave", "file_name": "hr.md", "page": 3, "section_path": ["Leave"]}
    it = {"doc_id": "it", "text": "laptop"}
    pts = [
        VectorPoint(str(uuid.uuid4()), embedder.embed_query("parental leave weeks"), hr),
        VectorPoint(str(uuid.uuid4()), embedder.embed_query("lost laptop"), it),
    ]
    index.upsert(pts)
    hits = index.search(embedder.embed_query("parental leave"), k=2)
    assert hits[0].chunk_id == pts[0].chunk_id
    assert (hits[0].file_name, hits[0].page, hits[0].section_path) == ("hr.md", 3, ("Leave",))
    assert hits[0].scores["vector"] > hits[1].scores["vector"]
    assert [h.doc_id for h in index.search(embedder.embed_query("parental"), doc_ids=["it"])] == ["it"]
    assert index.search(embedder.embed_query("x"), doc_ids=[]) == []
