"""FastAPI application:  uvicorn askdocs.api.main:app --reload"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..services import Services
from ..tracing import setup_tracing
from .errors import install_error_handlers
from .jobs import JobStore
from .routes import router


def create_app(services: Services | None = None) -> FastAPI:
    services = services or Services()
    setup_tracing(services.settings.tracing_enabled, services.settings.otel_endpoint)
    app = FastAPI(
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
