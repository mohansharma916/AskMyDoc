from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

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
    llm_provider: str = "anthropic"  # anthropic | ollama
    llm_model: str = "claude-opus-5-5"
    llm_api_key: str = ""  # falls back to ANTHROPIC_API_KEY when empty
    llm_effort: str = "low"
    llm_temperature: float = 0.1  # sent only to providers that accept it (Ollama)
    llm_timeout_s: float = 30.0
    ollama_url: str = "http://localhost:11434"

    # Prompts
    prompts_dir: Path = PROJECT_ROOT / "prompts"
    prompt_version: str = "answer_v1"

    # Retrieval depth
    retrieve_k: int = 20
    rerank_k: int = 5
    abstain_threshold: float = 0.1  # min best rerank score; tune with python -m eval.tune_threshold


@lru_cache
def get_settings() -> Settings:
    return Settings()
