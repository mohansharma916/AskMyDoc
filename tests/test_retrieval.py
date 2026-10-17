import time

import pytest

from askdocs.ingest.indexer import Indexer
from askdocs.retrieve.bm25 import BM25Index
from askdocs.retrieve.fusion import reciprocal_rank_fusion
from askdocs.retrieve.hybrid import HybridRetriever, StageTimeout
from askdocs.retrieve.types import Candidate
from askdocs.retrieve.vector import QdrantIndex, make_client
from askdocs.store.db import Database


def c(cid, **scores):
    return Candidate(chunk_id=cid, doc_id="d", text=cid, scores=scores)


def test_rrf_scores_and_order():
    bm25 = [c("a", bm25=9.0), c("b", bm25=5.0), c("c", bm25=1.0)]
    vector = [c("b", vector=0.9), c("d", vector=0.8)]
    fused = reciprocal_rank_fusion([bm25, vector], k=60)
    assert [x.chunk_id for x in fused] == ["b", "a", "d", "c"]
    b = fused[0]
    assert b.scores["rrf"] == pytest.approx(1 / 62 + 1 / 61)
    assert b.scores["bm25"] == 5.0 and b.scores["vector"] == 0.9
    assert bm25[1].scores == {"bm25": 5.0}  # inputs are not mutated


def test_rrf_top_n_and_empty():
    assert len(reciprocal_rank_fusion([[c(str(i)) for i in range(30)]], top_n=20)) == 20
    assert reciprocal_rank_fusion([[], []]) == []


DOCS = {
    "leave.md": b"# Leave\n\nPrimary caregivers receive 20 weeks of parental leave.\n",
    "it.txt": b"Lost laptops must be reported within 24 hours via the help channel.",
    "travel.md": b"# Travel\n\nEconomy class is required for flights shorter than six hours.\n",
}


@pytest.fixture
def retriever(embedder):
    db = Database("sqlite:///:memory:")
    vectors = QdrantIndex(make_client(":memory:"), "chunks", embedder.dim)
    bm25 = BM25Index()
    Indexer(db, vectors, embedder, bm25).ingest_files((n, d, n) for n, d in DOCS.items())
    return HybridRetriever(db, bm25, vectors, embedder)


@pytest.mark.parametrize("mode", ["bm25", "vector", "hybrid"])
def test_each_mode_finds_the_right_chunk(retriever, mode):
    hits = retriever.retrieve("parental leave weeks", k=3, mode=mode)
    assert hits[0].doc_id == "leave"
    assert hits[0].file_name == "leave.md"


def test_hybrid_merges_scores_and_respects_filters(retriever):
    hits = retriever.retrieve("laptops reported", mode="hybrid")
    assert hits[0].doc_id == "it"
    assert {"bm25", "vector", "rrf"} <= hits[0].scores.keys()
    filtered = retriever.retrieve("laptops reported", doc_ids=["travel"])
    assert {h.doc_id for h in filtered} == {"travel"}


def test_retrieve_timeout(retriever, monkeypatch):
    retriever.timeout_s = 0.05
    monkeypatch.setattr(retriever.bm25, "search", lambda *a, **k: time.sleep(0.3) or [])
    with pytest.raises(StageTimeout, match="retrieve"):
        retriever.retrieve("leave", mode="bm25")
