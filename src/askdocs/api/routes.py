import json
import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from ..config import Settings
from ..ingest.parsers import SUPPORTED_EXTENSIONS
from ..services import RUNTIME_KEYS, Services
from ..store.models import Chunk, Document, Feedback, Trace
from .errors import APIError, classify, error_body
from .jobs import JobStore
from .schemas import (
    AskRequest,
    AskResponse,
    DocumentList,
    DocumentOut,
    ErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    IngestJob,
    LLMStatus,
    RuntimeSettings,
    SettingsResponse,
    SettingsUpdate,
)

ERRORS = {code: {"model": ErrorResponse} for code in (400, 403, 404, 413, 429, 500, 504)}

router = APIRouter(prefix="/api/v1", responses=ERRORS)


def services(request: Request) -> Services:
    return request.app.state.services


def jobs(request: Request) -> JobStore:
    return request.app.state.jobs


# --- Health -------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(request: Request) -> HealthResponse:
    svc = services(request)
    s = svc.settings
    database = svc.db.ping()
    qdrant = svc.vectors.ping()
    documents = chunks = 0
    if database:
        with svc.db.session() as session:
            documents = session.scalar(select(func.count()).select_from(Document))
            chunks = session.scalar(select(func.count()).select_from(Chunk))
    configured = s.llm_provider != "anthropic" or bool(s.llm_api_key or os.getenv("ANTHROPIC_API_KEY"))
    return HealthResponse(
        status="ok" if database and qdrant and configured else "degraded",
        database=database,
        qdrant=qdrant,
        llm=LLMStatus(provider=s.llm_provider, model=s.llm_model, configured=configured),
        documents=documents,
        chunks=chunks,
    )


# --- Ingest -------------------------------------------------------------------


def _read_upload(upload: UploadFile, limit_bytes: int) -> bytes:
    data = upload.file.read(limit_bytes + 1)
    if len(data) > limit_bytes:
        raise APIError(413, "file_too_large", f"'{upload.filename}' exceeds the {limit_bytes // 2**20} MB limit.")
    return data


def _files_under(path_str: str, root: Path) -> list[tuple[str, bytes, str]]:
    path = (root / path_str).resolve() if not Path(path_str).is_absolute() else Path(path_str).resolve()
    if not path.is_relative_to(root.resolve()):
        raise APIError(400, "invalid_request", f"path must be inside the ingest root ({root}).")
    if not path.exists():
        raise APIError(404, "not_found", f"Path not found: {path_str}")
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    return [(f.name, f.read_bytes(), str(f)) for f in files if f.suffix.lower() in SUPPORTED_EXTENSIONS]


@router.post("/ingest", response_model=IngestJob, status_code=202, tags=["ingest"])
def ingest(
    request: Request,
    files: Annotated[list[UploadFile] | None, File(description="Files to index")] = None,
    path: Annotated[str | None, Form(description="Folder or file under INGEST_ROOT to index")] = None,
) -> IngestJob:
    s = services(request).settings
    batch: list[tuple[str, bytes, str]] = []
    for upload in files or []:
        name = upload.filename or "upload"
        batch.append((name, _read_upload(upload, s.max_upload_mb * 2**20), f"upload://{name}"))
    if path:
        batch += _files_under(path, s.ingest_root)
    if not batch:
        raise APIError(400, "invalid_request", "Provide files or a path with supported documents.")
    return jobs(request).submit(batch)


@router.get("/ingest/{job_id}", response_model=IngestJob, tags=["ingest"])
def ingest_status(job_id: str, request: Request) -> IngestJob:
    job = jobs(request).get(job_id)
    if job is None:
        raise APIError(404, "not_found", f"Unknown job_id '{job_id}'.")
    return job


# --- Documents ----------------------------------------------------------------


@router.get("/documents", response_model=DocumentList, tags=["documents"])
def documents(request: Request) -> DocumentList:
    docs = services(request).indexer.list_documents()
    return DocumentList(
        documents=[
            DocumentOut(
                doc_id=d.doc_id, file_name=d.file_name, title=d.title, chunks=len(d.chunks), ingested_at=d.ingested_at
            )
            for d in docs
        ]
    )


@router.delete("/documents/{doc_id}", status_code=204, tags=["documents"])
def delete_document(doc_id: str, request: Request) -> None:
    if not services(request).indexer.delete(doc_id):
        raise APIError(404, "not_found", f"Unknown doc_id '{doc_id}'.")


# --- Ask ----------------------------------------------------------------------


def _doc_filter(request: Request, body: AskRequest) -> list[str] | None:
    doc_ids = body.filters.doc_ids if body.filters else None
    if not doc_ids:
        return None
    with services(request).db.session() as session:
        known = set(session.scalars(select(Document.doc_id).where(Document.doc_id.in_(doc_ids))))
    if unknown := sorted(set(doc_ids) - known):
        raise APIError(400, "invalid_request", f"Unknown doc_ids in filters: {', '.join(unknown)}")
    return doc_ids


@router.post("/ask", response_model=AskResponse, tags=["ask"])
def ask(body: AskRequest, request: Request) -> dict:
    doc_ids = _doc_filter(request, body)
    return services(request).pipeline.ask(body.question, top_k=body.top_k, doc_ids=doc_ids).to_dict()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post(
    "/ask/stream",
    tags=["ask"],
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "meta, token, retry, done or error events"}},
)
def ask_stream(body: AskRequest, request: Request) -> StreamingResponse:
    doc_ids = _doc_filter(request, body)  # validation errors are returned as normal JSON errors
    pipeline = services(request).pipeline

    def events():
        try:
            for event in pipeline.ask_stream(body.question, top_k=body.top_k, doc_ids=doc_ids):
                yield _sse(event.type, event.data)
        except Exception as exc:  # the response has started, so report errors as an event
            status, code, message = classify(exc)
            yield _sse("error", {**error_body(code, message)["error"], "status": status})

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)


# --- Developer settings -------------------------------------------------------


def _runtime(s: Settings) -> RuntimeSettings:
    values = {k: getattr(s, k) for k in RUNTIME_KEYS - {"llm_api_key"}}
    return RuntimeSettings(**values, llm_api_key_set=bool(s.llm_api_key))


def _settings_response(svc: Services) -> SettingsResponse:
    s = svc.settings
    return SettingsResponse(
        editable=s.dev_settings_enabled,
        settings=_runtime(s),
        defaults=_runtime(svc.initial_settings),
        restart_required={
            "embed_model": s.embed_model,
            "qdrant_url": s.qdrant_url,
            "qdrant_collection": s.qdrant_collection,
            "cors_origins": s.cors_origins,
            "tracing_enabled": s.tracing_enabled,
            "otel_endpoint": s.otel_endpoint,
        },
        prompt_versions=sorted(p.stem for p in s.prompts_dir.glob("*.txt")),
    )


def _configure(svc: Services, changes: dict) -> None:
    if not svc.settings.dev_settings_enabled:
        raise APIError(403, "forbidden", "Developer settings are disabled (DEV_SETTINGS_ENABLED=false).")
    try:
        svc.configure(**changes)
    except (ValueError, FileNotFoundError) as exc:
        raise APIError(400, "invalid_request", str(exc)) from exc


@router.get("/settings", response_model=SettingsResponse, tags=["system"])
def get_settings(request: Request) -> SettingsResponse:
    return _settings_response(services(request))


@router.patch("/settings", response_model=SettingsResponse, tags=["system"])
def update_settings(body: SettingsUpdate, request: Request) -> SettingsResponse:
    """Change runtime settings in memory; they last until the server restarts."""
    svc = services(request)
    _configure(svc, body.model_dump(exclude_none=True))
    return _settings_response(svc)


@router.post("/settings/reset", response_model=SettingsResponse, tags=["system"])
def reset_settings(request: Request) -> SettingsResponse:
    """Restore the settings the server started with."""
    svc = services(request)
    _configure(svc, {k: getattr(svc.initial_settings, k) for k in RUNTIME_KEYS})
    return _settings_response(svc)


# --- Feedback -----------------------------------------------------------------


@router.post("/feedback", response_model=FeedbackResponse, status_code=201, tags=["feedback"])
def feedback(body: FeedbackRequest, request: Request) -> FeedbackResponse:
    """Rate an answer; rating the same query again replaces the earlier rating."""
    with services(request).db.session() as session:
        trace = session.get(Trace, body.query_id)
        if trace is None:
            raise APIError(404, "not_found", f"Unknown query_id '{body.query_id}'.")
        row = session.get(Feedback, body.query_id) or Feedback(query_id=body.query_id)
        row.question, row.answer = trace.question, trace.answer
        row.cited_chunk_ids = [c["chunk_id"] for c in trace.citations]
        row.rating, row.comment = body.rating, body.comment
        session.add(row)
        session.flush()
        return FeedbackResponse(query_id=row.query_id, rating=row.rating, created_at=row.created_at)
