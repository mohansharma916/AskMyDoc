"""Wires components together from settings. Every component can be overridden,
which is how tests swap in fakes (no model downloads, in-memory stores)."""

from functools import cached_property

from .config import Settings, get_settings
from .ingest.indexer import Indexer
from .retrieve.bm25 import BM25Index
from .retrieve.embeddings import Embedder, SentenceTransformerEmbedder
from .retrieve.vector import QdrantIndex, make_client
from .store.db import Database


class Services:
    def __init__(self, settings: Settings | None = None, **overrides):
        self.settings = settings or get_settings()
        for name, value in overrides.items():
            if not hasattr(type(self), name):
                raise TypeError(f"Unknown service override: {name}")
            self.__dict__[name] = value  # pre-populates the cached_property

    @cached_property
    def db(self) -> Database:
        return Database(self.settings.database_url)

    @cached_property
    def embedder(self) -> Embedder:
        return SentenceTransformerEmbedder(self.settings.embed_model, self.settings.embed_query_prefix)

    @cached_property
    def vectors(self) -> QdrantIndex:
        client = make_client(self.settings.qdrant_url)
        return QdrantIndex(client, self.settings.qdrant_collection, self.embedder.dim)

    @cached_property
    def bm25(self) -> BM25Index:
        index = BM25Index()
        index.rebuild_from_db(self.db)
        return index

    @cached_property
    def indexer(self) -> Indexer:
        return Indexer(
            self.db,
            self.vectors,
            self.embedder,
            self.bm25,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
