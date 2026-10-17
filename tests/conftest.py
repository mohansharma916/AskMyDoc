import hashlib
import math
import re

import pytest


class HashEmbedder:
    """Deterministic bag-of-words embedder so unit tests never download models."""

    dim = 64

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for word in re.findall(r"\w+", text.lower()):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture
def embedder():
    return HashEmbedder()


class FakeLLM:
    """Replies with scripted answers in order; records every call."""

    model = "fake-llm"

    def __init__(self, *replies: str):
        self.replies = list(replies) or ["Primary caregivers receive 20 weeks of parental leave [1]."]
        self.calls: list[list[dict]] = []

    def _next(self, messages):
        from askdocs.generate.llm import Completion, Usage

        self.calls.append([dict(m) for m in messages])
        text = self.replies[min(len(self.calls), len(self.replies)) - 1]
        return Completion(text, self.model, Usage(100, 10, 0.001))

    def complete(self, system, messages):
        return self._next(messages)

    def stream(self, system, messages):
        completion = self._next(messages)
        for i in range(0, len(completion.text), 7):
            yield completion.text[i : i + 7]
        yield completion


class OverlapReranker:
    """Scores by query-word overlap so tests can steer abstention without a model."""

    def rerank(self, query, candidates):
        from askdocs.retrieve.bm25 import tokenize
        from askdocs.retrieve.types import Candidate

        q = set(tokenize(query))
        out = []
        for c in candidates:
            score = len(q & set(tokenize(c.text))) / (len(q) or 1)
            out.append(Candidate(**{**c.__dict__, "scores": {**c.scores, "rerank": score}}))
        return sorted(out, key=lambda c: c.scores["rerank"], reverse=True)


DOCS = {
    "leave.md": b"# Leave\n\nPrimary caregivers receive 20 weeks of parental leave.\n\n"
    b"## Sick leave\n\nEmployees receive up to 10 paid sick days per year.\n",
    "it.txt": b"Lost laptops must be reported within 24 hours via the help channel.",
}


@pytest.fixture
def make_services(embedder):
    from askdocs.config import Settings
    from askdocs.services import Services

    def factory(llm=None, reranker=None, ingest=True, **settings):
        s = Settings(database_url="sqlite:///:memory:", qdrant_url=":memory:", **settings)
        services = Services(s, embedder=embedder, llm=llm or FakeLLM(), reranker=reranker or OverlapReranker())
        if ingest:
            services.indexer.ingest_files((n, d, n) for n, d in DOCS.items())
        return services

    return factory
