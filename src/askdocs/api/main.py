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


def create_app(services: Services | None = None) -> FastAPI:
    services = services or Services()
    setup_tracing(services.settings.tracing_enabled, services.settings.otel_endpoint)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if services.settings.warmup_models:
            threading.Thread(target=warm_up, args=(services,), name="warmup", daemon=True).start()
        yield

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
    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
