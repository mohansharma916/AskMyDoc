from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    anthropic_api_key: str = ""
    cohere_api_key: str = ""

    llm_model: str = "claude-opus-5-5"
    llm_effort: str = "medium"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    cohere_rerank_model: str = "rerank-v3.5"
    reranker: str = "cohere"
    local_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    weaviate_host: str = "localhost"
    weaviate_http_port: int = 8080
    weaviate_grpc_port: int = 50051
    weaviate_collection: str = "DocumentChunk"

    chunk_size: int = 800
    chunk_overlap: int = 100

    top_k: int = 5
    hybrid_candidates: int = 20
    hybrid_alpha: float = 0.5
    rerank_top_n: int = 5
    rerank_min_score: float = 0.2

    threshold_faithfulness: float = 0.80
    threshold_answer_relevancy: float = 0.70
    threshold_context_recall: float = 0.70

    prompts_file: Path = BACKEND_DIR / "prompts.yaml"
    golden_file: Path = DATA_DIR / "golden_dataset.json"

    cors_origins: str = "http://localhost:5173"

    @property
    def thresholds(self) -> dict[str, float]:
        return {
            "faithfulness": self.threshold_faithfulness,
            "answer_relevancy": self.threshold_answer_relevancy,
            "context_recall": self.threshold_context_recall,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
