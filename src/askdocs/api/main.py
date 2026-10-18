"""FastAPI application:  uvicorn askdocs.api.main:app --reload"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..retrieve.types import Candidate
from ..services import Services
from ..tracing import setup_tracing
from .errors import install_error_handlers
from .jobs import JobStore
from .routes import router

log = logging.getLogger(__name__)


def warm_up(services: Services) -> None:
    """Load the embedding and reranker models so the first request doesn't pay for it."""
    try:
        services.embedder.embed_query("warm up")
        services.reranker.rerank("warm up", [Candidate("warmup", "warmup", "warm up")])
        services.bm25  # noqa: B018 - builds the keyword index
    except Exception:
        log.exception("model warm-up failed; models will load on first request")


def sweep_sessions(services: Services, jobs: JobStore, stop: threading.Event) -> None:
    """Every SESSION_SWEEP_S, delete sessions idle for longer than SESSION_TTL_S."""
    while not stop.wait(services.settings.session_sweep_s):
        try:
            busy = jobs.active_sessions()
            for session_id in busy:  # a long ingest keeps its session alive
                services.sessions.get(session_id, touch=True)
            services.sessions.sweep(keep=busy)
        except Exception:
            log.exception("session sweep failed")


class NoStoreAPIResponses:
    """Mark API responses uncacheable: they depend on the X-Session-Id header, and a browser that
    cached one session's 410 would replay it for the next session. Pure ASGI, so SSE still streams."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)

        async def send_no_store(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"]
                message = {**message, "headers": [*headers, (b"cache-control", b"no-store")]}
            await send(message)

        await self.app(scope, receive, send_no_store)


def create_app(services: Services | None = None) -> FastAPI:
    services = services or Services()
    setup_tracing(services.settings.tracing_enabled, services.settings.otel_endpoint)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if services.settings.warmup_models:
            threading.Thread(target=warm_up, args=(services,), name="warmup", daemon=True).start()
        stop = threading.Event()
        sweeper = threading.Thread(
            target=sweep_sessions, args=(services, app.state.jobs, stop), name="session-sweep", daemon=True
        )
        sweeper.start()
        yield
        stop.set()

    app = FastAPI(
        lifespan=lifespan,
        title="Ask My Docs",
        version=__version__,
        description="Cited answers from one document collection: hybrid retrieval, reranking, enforced citations.",
    )
    app.state.services = services
    app.state.jobs = JobStore(services)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in services.settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(NoStoreAPIResponses)
    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
