from functools import cached_property
from typing import Protocol

from sentence_transformers import SentenceTransformer


class Embedder(Protocol):
    @property
    def dim(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    """Local embedding model. BGE models expect an instruction prefix on queries only."""

    def __init__(self, model_name: str, query_prefix: str = "", batch_size: int = 32):
        self.model_name = model_name
        self.query_prefix = query_prefix
        self.batch_size = batch_size

    @cached_property
    def _model(self) -> SentenceTransformer:
        return SentenceTransformer(self.model_name)

    @cached_property
    def dim(self) -> int:
        return len(self.embed_query("dimension probe"))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode(self.query_prefix + text, normalize_embeddings=True)
        return vector.tolist()
