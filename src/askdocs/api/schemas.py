from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ErrorDetail(BaseModel):
    code: str
    message: str
    trace_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# --- Ingest / documents -------------------------------------------------------


class IngestFileResult(BaseModel):
    doc_id: str
    file_name: str
    status: Literal["indexed", "updated", "unchanged", "failed"]
    chunks: int
    error: str | None = None


class IngestCounts(BaseModel):
    indexed: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    chunks: int = 0


class IngestJob(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    files: int
    counts: IngestCounts = Field(default_factory=IngestCounts)
    results: list[IngestFileResult] = []
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class DocumentOut(BaseModel):
    doc_id: str
    file_name: str
    title: str
    chunks: int
    ingested_at: datetime
    source_type: Literal["preloaded", "user_upload"] = "preloaded"


class DocumentList(BaseModel):
    documents: list[DocumentOut]


class ChunkOut(BaseModel):
    chunk_id: str
    page: int | None = None
    section_path: list[str] = Field(default_factory=list)
    text: str
    token_count: int
    position: int


class DocumentDetail(BaseModel):
    doc_id: str
    file_name: str
    title: str
    source_uri: str
    source_type: Literal["preloaded", "user_upload"] = "preloaded"
    chunks: list[ChunkOut] = Field(default_factory=list)
    chunk_count: int = 0
    full_text: str = ""
    has_file: bool = False
    file_url: str | None = None
    ingested_at: datetime


# --- Ask ----------------------------------------------------------------------


class Filters(BaseModel):
    doc_ids: list[str] | None = None


class AskRequest(BaseModel):
    question: str = Field(max_length=2000)
    top_k: int | None = Field(None, ge=1, le=20, description="Chunks shown to the LLM; defaults to RERANK_K")
    filters: Filters | None = None

    @field_validator("question")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be empty")
        return v.strip()


class CitationOut(BaseModel):
    n: int
    chunk_id: str
    doc_id: str
    file_name: str
    page: int | None
    section_path: list[str]
    snippet: str


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


class AskResponse(BaseModel):
    query_id: str
    question: str
    answer: str
    abstained: bool
    abstain_reason: str | None
    citations: list[CitationOut]
    usage: UsageOut
    latency_ms: dict[str, int]
    model: str | None
    prompt_version: str
    trace_id: str | None = None


# --- Feedback -----------------------------------------------------------------


class FeedbackRequest(BaseModel):
    query_id: str
    rating: Literal["helpful", "not_helpful"]
    comment: str | None = Field(None, max_length=2000)


class FeedbackResponse(BaseModel):
    query_id: str
    rating: Literal["helpful", "not_helpful"]
    created_at: datetime


# --- Health -------------------------------------------------------------------


class LLMStatus(BaseModel):
    provider: str
    model: str
    configured: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    qdrant: bool
    llm: LLMStatus
    documents: int
    chunks: int


# --- Developer settings -------------------------------------------------------

LLMProvider = Literal["anthropic", "openai", "groq", "ollama"]
LLMEffort = Literal["low", "medium", "high", "xhigh", "max"]


class RuntimeSettings(BaseModel):
    """Settings that apply to the next request without a restart (see services.RUNTIME_SETTINGS)."""

    llm_provider: LLMProvider
    llm_model: str
    api_keys_set: dict[str, bool]  # per provider; the keys themselves are write-only
    llm_effort: LLMEffort
    llm_temperature: float
    llm_timeout_s: float
    ollama_url: str
    openai_base_url: str
    rerank_model: str
    prompt_version: str
    chunk_size: int
    chunk_overlap: int
    retrieve_k: int
    rerank_k: int
    abstain_threshold: float
    max_upload_mb: int


class SettingsUpdate(BaseModel):
    """Partial update; omitted fields keep their value. An empty API key clears it."""

    model_config = ConfigDict(extra="forbid")

    llm_provider: LLMProvider | None = None
    llm_model: str | None = Field(None, min_length=1, max_length=200)
    llm_api_key: str | None = Field(None, max_length=500)  # Anthropic
    openai_api_key: str | None = Field(None, max_length=500)
    groq_api_key: str | None = Field(None, max_length=500)
    llm_effort: LLMEffort | None = None
    llm_temperature: float | None = Field(None, ge=0, le=2)
    llm_timeout_s: float | None = Field(None, gt=0, le=600)
    ollama_url: str | None = Field(None, pattern=r"^https?://\S+$", max_length=500)
    openai_base_url: str | None = Field(None, pattern=r"^https?://\S+$", max_length=500)
    rerank_model: str | None = Field(None, min_length=1, max_length=200)
    prompt_version: str | None = Field(None, pattern=r"^[\w.-]+$", max_length=100)
    chunk_size: int | None = Field(None, ge=64, le=4096)
    chunk_overlap: int | None = Field(None, ge=0, le=1024)
    retrieve_k: int | None = Field(None, ge=1, le=100)
    rerank_k: int | None = Field(None, ge=1, le=20)
    abstain_threshold: float | None = Field(None, ge=0, le=1)
    max_upload_mb: int | None = Field(None, ge=1, le=500)


class SettingsResponse(BaseModel):
    editable: bool  # DEV_SETTINGS_ENABLED
    settings: RuntimeSettings
    defaults: RuntimeSettings  # values the server started with
    restart_required: dict[str, str | int | float | bool]  # shown read-only: change in .env and restart
    prompt_versions: list[str]
