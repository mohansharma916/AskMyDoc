from functools import cached_property
from typing import Protocol

import torch
from sentence_transformers import CrossEncoder

from ..retrieve.types import Candidate


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]: ...


def rerank_text(c: Candidate) -> str:
    """Give the cross-encoder the section context the chunk text may lack."""
    return f"{c.section}\n{c.text}" if c.section else c.text


class CrossEncoderReranker:
    """Scores (question, chunk) pairs with a cross-encoder; scores are sigmoid probabilities in [0, 1]."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base", batch_size: int = 16):
        self.model_name = model_name
        self.batch_size = batch_size

    @cached_property
    def _model(self) -> CrossEncoder:
        return CrossEncoder(self.model_name)

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        """Return all candidates sorted by rerank score (callers keep the top k)."""
        if not candidates:
            return []
        scores = self._model.predict(
            [(query, rerank_text(c)) for c in candidates],
            batch_size=self.batch_size,
            activation_fn=torch.nn.Sigmoid(),
        )
        reranked = [
            Candidate(**{**c.__dict__, "scores": {**c.scores, "rerank": float(s)}})
            for c, s in zip(candidates, scores, strict=True)
        ]
        reranked.sort(key=lambda c: c.scores["rerank"], reverse=True)
        return reranked
