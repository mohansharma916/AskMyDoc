from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from ..store.db import Database
from .bm25 import BM25Index
from .embeddings import Embedder
from .fusion import reciprocal_rank_fusion
from .types import Candidate
from .vector import QdrantIndex

RetrievalMode = Literal["bm25", "vector", "hybrid"]


class StageTimeout(TimeoutError):
    def __init__(self, stage: str, seconds: float):
        super().__init__(f"{stage} exceeded {seconds:g}s")
        self.stage = stage


class HybridRetriever:
    """BM25 and vector search run in parallel, then fuse with RRF."""

    def __init__(
        self,
        db: Database,
        bm25: BM25Index,
        vectors: QdrantIndex,
        embedder: Embedder,
        timeout_s: float = 10.0,
    ):
        self.db = db
        self.bm25 = bm25
        self.vectors = vectors
        self.embedder = embedder
        self.timeout_s = timeout_s
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="retrieve")

    def _vector(self, query: str, k: int, doc_ids: list[str] | None) -> list[Candidate]:
        return self.vectors.search(self.embedder.embed_query(query), k, doc_ids)

    def _bm25(self, query: str, k: int, doc_ids: list[str] | None) -> list[Candidate]:
        self.bm25.ensure_fresh(self.db)  # picks up documents ingested by another process
        return self.bm25.search(query, k, doc_ids)

    def retrieve(
        self,
        query: str,
        k: int = 20,
        doc_ids: list[str] | None = None,
        mode: RetrievalMode = "hybrid",
    ) -> list[Candidate]:
        searches = {
            "bm25": [self._bm25],
            "vector": [self._vector],
            "hybrid": [self._bm25, self._vector],
        }[mode]
        futures = [self._pool.submit(search, query, k, doc_ids) for search in searches]
        try:
            rankings = [f.result(timeout=self.timeout_s) for f in futures]
        except TimeoutError as exc:
            raise StageTimeout("retrieve", self.timeout_s) from exc
        if len(rankings) == 1:
            return rankings[0][:k]
        return reciprocal_rank_fusion(rankings, top_n=k)
