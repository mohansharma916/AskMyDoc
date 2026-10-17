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

    # Chunking (tokens)
    chunk_size: int = 512
    chunk_overlap: int = 64


@lru_cache
def get_settings() -> Settings:
    return Settings()
