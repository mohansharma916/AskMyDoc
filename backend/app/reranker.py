"""Cross-encoder re-ranking behind a small interface (ADR 3).

Cohere is the default; a local sentence-transformers cross-encoder can be
swapped in with RERANKER=local and needs no API key.
"""

import math
from abc import ABC, abstractmethod
from functools import lru_cache

from .config import get_settings


class Reranker(ABC):
    name: str

    @abstractmethod
    def scores(self, query: str, texts: list[str]) -> list[float]:
        """Relevance score in [0, 1] for each text, in input order."""

    def rerank(self, query: str, chunks: list[dict], top_n: int) -> list[dict]:
        if not chunks:
            return []
        scored = [
            {**chunk, "retrieval_score": chunk["score"], "score": round(score, 4)}
            for chunk, score in zip(chunks, self.scores(query, [c["text"] for c in chunks]))
        ]
        scored.sort(key=lambda c: c["score"], reverse=True)
        return scored[:top_n]


class CohereReranker(Reranker):
    def __init__(self, api_key: str, model: str):
        import cohere

        if not api_key:
            raise RuntimeError("COHERE_API_KEY is not set. Set it, or use RERANKER=local.")
        self._client = cohere.ClientV2(api_key=api_key)
        self._model = model
        self.name = f"cohere:{model}"

    def scores(self, query: str, texts: list[str]) -> list[float]:
        response = self._client.rerank(model=self._model, query=query, documents=texts, top_n=len(texts))
        result = [0.0] * len(texts)
        for item in response.results:
            result[item.index] = item.relevance_score
        return result


class LocalCrossEncoderReranker(Reranker):
    def __init__(self, model: str):
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model)
        self.name = f"local:{model}"

    def scores(self, query: str, texts: list[str]) -> list[float]:
        logits = self._model.predict([(query, t) for t in texts])
        return [1 / (1 + math.exp(-float(x))) for x in logits]


@lru_cache
def get_reranker() -> Reranker:
    s = get_settings()
    if s.reranker == "local":
        return LocalCrossEncoderReranker(s.local_rerank_model)
    return CohereReranker(s.cohere_api_key, s.cohere_rerank_model)
