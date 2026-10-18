import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select

from ..config import API_KEY_FIELDS, PROJECT_ROOT, Settings
from ..ingest.parsers import SUPPORTED_EXTENSIONS
from ..services import RUNTIME_KEYS, Services
from ..store.models import Chunk, Document, Feedback, Trace
from .errors import APIError, classify, error_body
from .jobs import JobStore
from .schemas import (
    AskRequest,
    AskResponse,
    ChunkOut,
    DocumentDetail,
    DocumentList,
    DocumentOut,
    ErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    IngestJob,
    LLMStatus,
    RuntimeSettings,
    SessionOut,
    SettingsResponse,
    SettingsUpdate,
)

ERRORS = {code: {"model": ErrorResponse} for code in (400, 403, 404, 410, 413, 429, 500, 504)}
SESSION_HEADER = "X-Session-Id"

router = APIRouter(prefix="/api/v1", responses=ERRORS)


def services(request: Request) -> Services:
    return request.app.state.services


def jobs(request: Request) -> JobStore:
    return request.app.state.jobs


def session_id(request: Request, required: bool = False, touch: bool = False) -> str | None:
    """The caller's browser session (X-Session-Id header, or ?session_id= for file links).

    Without one, a request sees only shared documents. `touch` marks user activity,
    which postpones the session's expiry.
    """
    sid = request.headers.get(SESSION_HEADER) or request.query_params.get("session_id")
    if not sid:
        if required:
            message = f"Start a session (POST /api/v1/sessions) and send its id in {SESSION_HEADER}."
            raise APIError(400, "session_required", message)
        return None
    if services(request).sessions.get(sid, touch=touch) is None:
        raise APIError(410, "session_expired", "This session expired after inactivity and its documents were deleted.")
    return sid


def _visible_document(session, doc_id: str, sid: str | None) -> Document:
    """The document if this session may see it (shared, or its own upload); 404 otherwise."""
    doc = session.get(Document, doc_id)
    if doc is None or doc.session_id not in (None, sid):
        raise APIError(404, "not_found", f"Unknown doc_id '{doc_id}'.")
    return doc


def _source_type(d: Document) -> str:
    return "user_upload" if d.session_id else "preloaded"


# --- Browser sessions ---------------------------------------------------------


def _session_out(info) -> SessionOut:
    return SessionOut(session_id=info.session_id, expires_at=info.expires_at, ttl_s=info.ttl_s)


@router.post("/sessions", response_model=SessionOut, status_code=201, tags=["sessions"])
def create_session(request: Request) -> SessionOut:
    """Start a private browser session; send its id as X-Session-Id on later requests."""
    return _session_out(services(request).sessions.create())


@router.get("/sessions/current", response_model=SessionOut, tags=["sessions"])
def current_session(request: Request) -> SessionOut:
    """The caller's session and when it expires (410 if it already has)."""
    sid = session_id(request, required=True)
    return _session_out(services(request).sessions.get(sid))


@router.post("/sessions/current/heartbeat", response_model=SessionOut, tags=["sessions"])
def heartbeat(request: Request) -> SessionOut:
    """Record user activity in the browser, postponing expiry."""
    sid = session_id(request, required=True, touch=True)
    return _session_out(services(request).sessions.get(sid))


@router.delete("/sessions/current", status_code=204, tags=["sessions"])
def end_session(request: Request) -> None:
    """End the session now and delete everything it uploaded."""
    services(request).sessions.purge(session_id(request, required=True))


# --- Health -------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(request: Request) -> HealthResponse:
    """System status; document and chunk counts cover what the caller's session can see."""
    svc = services(request)
    s = svc.settings
    database = svc.db.ping()
    qdrant = svc.vectors.ping()
    documents = chunks = 0
    if database:
        visible = svc.indexer.visible(session_id(request))
        with svc.db.session() as session:
            documents = session.scalar(select(func.count()).select_from(Document).where(visible))
            chunks = session.scalar(select(func.count()).select_from(Chunk).join(Document).where(visible))
    configured = s.llm_configured()
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
    """Index files into the caller's session; they are private to it and deleted when it expires."""
    sid = session_id(request, required=True, touch=True)
    svc = services(request)
    s = svc.settings
    batch: list[tuple[str, bytes, str]] = []
    upload_dir = svc.sessions.upload_dir(sid)
    upload_dir.mkdir(parents=True, exist_ok=True)
    for upload in files or []:
        name = Path(upload.filename or "upload").name or "upload"  # no directory parts from the client
        data = _read_upload(upload, s.max_upload_mb * 2**20)
        file_path = upload_dir / name
        file_path.write_bytes(data)
        batch.append((name, data, f"upload://{file_path}"))
    if path:
        batch += _files_under(path, s.ingest_root)
    if not batch:
        raise APIError(400, "invalid_request", "Provide files or a path with supported documents.")
    return jobs(request).submit(batch, sid)


@router.get("/ingest/{job_id}", response_model=IngestJob, tags=["ingest"])
def ingest_status(job_id: str, request: Request) -> IngestJob:
    job = jobs(request).get(job_id, session_id(request))
    if job is None:
        raise APIError(404, "not_found", f"Unknown job_id '{job_id}'.")
    return job


# --- Documents ----------------------------------------------------------------


def _resolve_doc_file_path(d: Document, s: Settings) -> Path | None:
    uri = d.source_uri or ""
    if uri.startswith("file://"):
        p = Path(uri.removeprefix("file://"))
        if p.is_file():
            return p
    elif uri.startswith("upload://"):
        raw_target = uri.removeprefix("upload://")
        p = Path(raw_target)
        if p.is_file():
            return p
        if d.session_id:  # never fall back to a same-named file from another session
            return None
        p2 = s.ingest_root / "uploads" / d.file_name
        if p2.is_file():
            return p2
        p3 = PROJECT_ROOT / "data" / "uploads" / d.file_name
        if p3.is_file():
            return p3
    else:
        p = Path(uri)
        if p.is_file():
            return p
    p_corpus = PROJECT_ROOT / "eval" / "corpus" / d.file_name
    if p_corpus.is_file():
        return p_corpus
    return None


@router.get("/documents", response_model=DocumentList, tags=["documents"])
def documents(request: Request) -> DocumentList:
    docs = services(request).indexer.list_documents(session_id(request))
    return DocumentList(
        documents=[
            DocumentOut(
                doc_id=d.doc_id,
                file_name=d.file_name,
                title=d.title,
                chunks=len(d.chunks),
                ingested_at=d.ingested_at,
                source_type=_source_type(d),
            )
            for d in docs
        ]
    )


@router.get("/documents/{doc_id}", response_model=DocumentDetail, tags=["documents"])
def get_document(doc_id: str, request: Request) -> DocumentDetail:
    s_settings = services(request).settings
    sid = session_id(request)
    with services(request).db.session() as s:
        d = _visible_document(s, doc_id, sid)
        chunks = [
            ChunkOut(
                chunk_id=c.chunk_id,
                page=c.page,
                section_path=c.section_path or [],
                text=c.text,
                token_count=c.token_count,
                position=c.position,
            )
            for c in d.chunks
        ]
        file_path = _resolve_doc_file_path(d, s_settings)
        has_file = file_path is not None and file_path.is_file()
        full_text = ""
        if has_file and file_path and not d.file_name.lower().endswith(".pdf"):
            try:
                full_text = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                full_text = "\n\n".join(c.text for c in d.chunks)
        else:
            full_text = "\n\n".join(c.text for c in d.chunks)

        return DocumentDetail(
            doc_id=d.doc_id,
            file_name=d.file_name,
            title=d.title,
            source_uri=d.source_uri or "",
            source_type=_source_type(d),
            chunks=chunks,
            chunk_count=len(chunks),
            full_text=full_text,
            has_file=has_file,
            # <iframe>/<a> can't send headers, so session uploads carry the session in the link
            file_url=(f"/api/v1/documents/{d.doc_id}/file" + (f"?session_id={sid}" if d.session_id else ""))
            if has_file
            else None,
            ingested_at=d.ingested_at,
        )


@router.get("/documents/{doc_id}/file", tags=["documents"])
def get_document_file(doc_id: str, request: Request) -> FileResponse:
    s_settings = services(request).settings
    with services(request).db.session() as s:
        d = _visible_document(s, doc_id, session_id(request))
        file_path = _resolve_doc_file_path(d, s_settings)
        if file_path is None or not file_path.is_file():
            raise APIError(404, "not_found", f"Source file for '{doc_id}' not found.")
        media_type = "application/pdf" if d.file_name.lower().endswith(".pdf") else None
        return FileResponse(
            file_path,
            media_type=media_type,
            filename=d.file_name,
            headers={"Content-Disposition": f'inline; filename="{d.file_name}"'},
        )


@router.delete("/documents/{doc_id}", status_code=204, tags=["documents"])
def delete_document(doc_id: str, request: Request) -> None:
    """Delete one of the session's own uploads; shared documents can't be deleted through the API."""
    sid = session_id(request, touch=True)
    with services(request).db.session() as s:
        doc = _visible_document(s, doc_id, sid)
    if doc.session_id is None:
        raise APIError(403, "forbidden", "Shared documents can't be deleted here.")
    services(request).indexer.delete(doc_id)


# --- Ask ----------------------------------------------------------------------


def _doc_filter(request: Request, body: AskRequest, sid: str | None) -> list[str]:
    """Documents to search: everything the session can see, narrowed by the request's filter."""
    visible = services(request).indexer.visible_doc_ids(sid)
    doc_ids = body.filters.doc_ids if body.filters else None
    if not doc_ids:
        return visible
    if unknown := sorted(set(doc_ids) - set(visible)):
        raise APIError(400, "invalid_request", f"Unknown doc_ids in filters: {', '.join(unknown)}")
    return doc_ids


@router.post("/ask", response_model=AskResponse, tags=["ask"])
def ask(body: AskRequest, request: Request) -> dict:
    sid = session_id(request, touch=True)
    doc_ids = _doc_filter(request, body, sid)
    result = services(request).pipeline.ask(body.question, top_k=body.top_k, doc_ids=doc_ids, session_id=sid)
    return result.to_dict()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post(
    "/ask/stream",
    tags=["ask"],
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "meta, token, retry, done or error events"}},
)
def ask_stream(body: AskRequest, request: Request) -> StreamingResponse:
    sid = session_id(request, touch=True)
    doc_ids = _doc_filter(request, body, sid)  # validation errors are returned as normal JSON errors
    pipeline = services(request).pipeline

    def events():
        try:
            for event in pipeline.ask_stream(body.question, top_k=body.top_k, doc_ids=doc_ids, session_id=sid):
                yield _sse(event.type, event.data)
        except Exception as exc:  # the response has started, so report errors as an event
            status, code, message = classify(exc)
            yield _sse("error", {**error_body(code, message)["error"], "status": status})

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)


# --- Developer settings -------------------------------------------------------


def _runtime(s: Settings) -> RuntimeSettings:
    values = {k: getattr(s, k) for k in RUNTIME_KEYS - set(API_KEY_FIELDS.values())}
    return RuntimeSettings(**values, api_keys_set={p: bool(s.provider_api_key(p)) for p in API_KEY_FIELDS})


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
    sid = session_id(request, touch=True)
    with services(request).db.session() as session:
        trace = session.get(Trace, body.query_id)
        if trace is None or trace.session_id != sid:
            raise APIError(404, "not_found", f"Unknown query_id '{body.query_id}'.")
        row = session.get(Feedback, body.query_id) or Feedback(query_id=body.query_id)
        row.question, row.answer = trace.question, trace.answer
        row.cited_chunk_ids = [c["chunk_id"] for c in trace.citations]
        row.rating, row.comment = body.rating, body.comment
        session.add(row)
        session.flush()
        return FeedbackResponse(query_id=row.query_id, rating=row.rating, created_at=row.created_at)
