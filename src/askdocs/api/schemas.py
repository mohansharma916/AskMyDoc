from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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


class DocumentList(BaseModel):
    documents: list[DocumentOut]


# --- Ask ----------------------------------------------------------------------


class Filters(BaseModel):
    doc_ids: list[str] | None = None


class AskRequest(BaseModel):
    question: str = Field(max_length=2000)
    top_k: int = Field(5, ge=1, le=10)
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
