"""Wires components together from settings. Every component can be overridden,
which is how tests swap in fakes (no model downloads, in-memory stores)."""

import threading
from functools import cached_property

from .config import Settings, get_settings
from .generate.llm import LLMClient, make_llm
from .generate.prompt import PromptTemplate, load_prompt
from .ingest.indexer import Indexer
from .pipeline import AskPipeline
from .rerank.cross_encoder import CrossEncoderReranker, Reranker
from .retrieve.bm25 import BM25Index
from .retrieve.embeddings import Embedder, SentenceTransformerEmbedder
from .retrieve.hybrid import HybridRetriever
from .retrieve.vector import QdrantIndex, make_client
from .store.db import Database

_LLM = {"llm_provider", "llm_model", "llm_api_key", "llm_effort", "llm_temperature", "llm_timeout_s", "ollama_url"}

# Settings that can change while the app runs, and the components built from them.
# Changing one rebuilds only those components; requests already in flight finish on the old ones.
RUNTIME_SETTINGS: dict[str, set[str]] = {
    "llm": _LLM,
    "prompt": {"prompt_version"},
    "reranker": {"rerank_model"},
    "indexer": {"chunk_size", "chunk_overlap"},
    "pipeline": _LLM | {"prompt_version", "rerank_model", "retrieve_k", "rerank_k", "abstain_threshold"},
    "": {"max_upload_mb"},  # read per request, nothing to rebuild
}
RUNTIME_KEYS = set().union(*RUNTIME_SETTINGS.values())


class Services:
    def __init__(self, settings: Settings | None = None, **overrides):
        self.settings = settings or get_settings()
        self.initial_settings = self.settings
        self._configure_lock = threading.Lock()
        for name, value in overrides.items():
            if not hasattr(type(self), name):
                raise TypeError(f"Unknown service override: {name}")
            self.__dict__[name] = value  # pre-populates the cached_property

    def configure(self, **changes) -> Settings:
        """Change runtime settings in memory and rebuild the components that depend on them.

        The LLM client and prompt are built before anything is swapped, so a bad
        provider or a missing prompt raises and leaves the running config intact.
        """
        if unknown := set(changes) - RUNTIME_KEYS:
            raise ValueError(f"Not changeable at runtime: {', '.join(sorted(unknown))}")
        with self._configure_lock:
            changed = {k for k, v in changes.items() if getattr(self.settings, k) != v}
            if not changed:
                return self.settings
            settings = self.settings.model_copy(update=changes)
            if settings.chunk_overlap >= settings.chunk_size:
                raise ValueError("chunk_overlap must be smaller than chunk_size.")
            if settings.rerank_k > settings.retrieve_k:
                raise ValueError("rerank_k must not exceed retrieve_k.")
            stale = {name for name, keys in RUNTIME_SETTINGS.items() if name and changed & keys}
            fresh = Services(settings)
            built = {name: getattr(fresh, name) for name in ("llm", "prompt") if name in stale}
            self.settings = settings
            for name in stale:
                self.__dict__.pop(name, None)
            self.__dict__.update(built)
            return settings

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

    @cached_property
    def retriever(self) -> HybridRetriever:
        return HybridRetriever(self.db, self.bm25, self.vectors, self.embedder)

    @cached_property
    def reranker(self) -> Reranker:
        return CrossEncoderReranker(self.settings.rerank_model)

    @cached_property
    def llm(self) -> LLMClient:
        s = self.settings
        return make_llm(
            s.llm_provider,
            s.llm_model,
            api_key=s.llm_api_key,
            effort=s.llm_effort,
            temperature=s.llm_temperature,
            timeout_s=s.llm_timeout_s,
            ollama_url=s.ollama_url,
        )

    @cached_property
    def prompt(self) -> PromptTemplate:
        return load_prompt(self.settings.prompts_dir, self.settings.prompt_version)

    @cached_property
    def pipeline(self) -> AskPipeline:
        s = self.settings
        return AskPipeline(
            self.retriever,
            self.reranker,
            self.llm,
            self.prompt,
            db=self.db,
            retrieve_k=s.retrieve_k,
            rerank_k=s.rerank_k,
            abstain_threshold=s.abstain_threshold,
        )
