"""Builds an isolated stack over the fixed corpus for evaluation runs.

Uses an in-memory SQLite database and, unless EVAL_QDRANT_URL points at a
server (as in CI), an in-memory Qdrant, so evals never touch local data.
"""

import os

from askdocs.config import Settings, get_settings
from askdocs.services import Services

from .build_golden import CORPUS


def eval_settings(**overrides) -> Settings:
    base = get_settings().model_dump()
    base.update(
        database_url="sqlite:///:memory:",
        qdrant_url=os.getenv("EVAL_QDRANT_URL", ":memory:"),
        qdrant_collection="eval_chunks",
    )
    base.update(overrides)
    return Settings(**base)


def build_eval_services(settings: Settings | None = None, **overrides) -> Services:
    services = Services(settings or eval_settings(), **overrides)
    if services.settings.qdrant_url != ":memory:":  # shared server: start from a clean collection
        client = services.vectors.client
        if client.collection_exists(services.vectors.collection):
            client.delete_collection(services.vectors.collection)
    summary = services.indexer.ingest_path(CORPUS)
    failed = [r for r in summary.results if r.status == "failed"]
    if failed:
        raise RuntimeError(f"Corpus ingestion failed: {failed}")
    return services
