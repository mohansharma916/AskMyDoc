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
