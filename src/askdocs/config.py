import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Setting that holds each provider's API key; keys are write-only in the settings API.
API_KEY_FIELDS = {"anthropic": "llm_api_key", "openai": "openai_api_key", "groq": "groq_api_key"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    # API
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 25
    ingest_root: Path = PROJECT_ROOT / "data"  # POST /ingest {path} may only read below this folder
    warmup_models: bool = True  # load embedding + reranker models at startup
    dev_settings_enabled: bool = True  # allow PATCH /settings (the UI's Developer settings); disable when exposed

    # Tracing (OTLP/HTTP: Phoenix at :6006 by default; Langfuse via its OTLP endpoint + OTEL_EXPORTER_OTLP_HEADERS)
    tracing_enabled: bool = False
    otel_endpoint: str = "http://localhost:6006/v1/traces"

    # Storage
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'askdocs.db'}"
    qdrant_url: str = "http://localhost:6333"  # or ":memory:" for tests / single-process runs
    qdrant_collection: str = "chunks"

    # Models
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_query_prefix: str = "Represent this sentence for searching relevant passages: "
    rerank_model: str = "BAAI/bge-reranker-base"

    # Chunking (tokens)
    chunk_size: int = 512
    chunk_overlap: int = 64

    # LLM
    llm_provider: str = "anthropic"  # anthropic | openai | groq | ollama
    llm_model: str = "claude-opus-5-5"
    llm_api_key: str = ""  # Anthropic key (also the eval judge's); falls back to ANTHROPIC_API_KEY when empty
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"  # or any OpenAI-compatible server
    groq_api_key: str = ""
    llm_effort: str = "low"
    llm_temperature: float = 0.1  # sent only to providers that accept it (Ollama)
    llm_timeout_s: float = 30.0
    ollama_url: str = "http://localhost:11434"

    # Prompts
    prompts_dir: Path = PROJECT_ROOT / "prompts"
    prompt_version: str = "answer_v3"

    # Retrieval depth
    retrieve_k: int = 20
    rerank_k: int = 5
    abstain_threshold: float = 0.03  # min best rerank score; tuned with python -m eval.tune_threshold

    def provider_api_key(self, provider: str | None = None) -> str:
        """The key for one provider (default: LLM_PROVIDER), so keys never cross providers."""
        field = API_KEY_FIELDS.get(provider or self.llm_provider)
        return getattr(self, field) if field else ""

    def llm_configured(self) -> bool:
        if self.llm_provider == "ollama":
            return True
        return bool(self.provider_api_key() or (self.llm_provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY")))


@lru_cache
def get_settings() -> Settings:
    return Settings()
