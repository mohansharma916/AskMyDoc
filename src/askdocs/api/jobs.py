"""Background ingestion jobs. One worker thread serialises writes to the indexes."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from ..services import Services
from .schemas import IngestCounts, IngestFileResult, IngestJob


class JobStore:
    def __init__(self, services: Services):
        self.services = services  # the indexer (and its models) load on the first job
        self._jobs: dict[str, IngestJob] = {}
        self._owners: dict[str, str | None] = {}  # job_id -> browser session that started it
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")

    def get(self, job_id: str, session_id: str | None = None) -> IngestJob | None:
        """The job, if it exists and was started by this session."""
        with self._lock:
            job = self._jobs.get(job_id)
            return job if job is not None and self._owners.get(job_id) == session_id else None

    def active_sessions(self) -> set[str]:
        """Sessions with an ingest still queued or running; they must not expire mid-ingest."""
        with self._lock:
            return {
                owner
                for job_id, owner in self._owners.items()
                if owner and self._jobs[job_id].status in ("queued", "running")
            }

    def submit(self, files: list[tuple[str, bytes, str]], session_id: str | None = None) -> IngestJob:
        job = IngestJob(
            job_id="j_" + uuid.uuid4().hex[:16], status="queued", files=len(files), created_at=datetime.now(UTC)
        )
        with self._lock:
            self._jobs[job.job_id] = job
            self._owners[job.job_id] = session_id
        self._pool.submit(self._run, job.job_id, files, session_id)
        return job

    def _update(self, job_id: str, **changes) -> None:
        with self._lock:
            self._jobs[job_id] = self._jobs[job_id].model_copy(update=changes)

    def _run(self, job_id: str, files: list[tuple[str, bytes, str]], session_id: str | None = None) -> None:
        self._update(job_id, status="running")
        try:
            summary = self.services.indexer.ingest_files(files, session_id=session_id)
        except Exception as exc:  # e.g. Qdrant down: the whole job fails
            self._update(job_id, status="failed", error=str(exc), finished_at=datetime.now(UTC))
            return
        counts = IngestCounts(
            indexed=summary.count("indexed"),
            updated=summary.count("updated"),
            unchanged=summary.count("unchanged"),
            failed=summary.count("failed"),
            chunks=summary.chunks,
        )
        results = [IngestFileResult(**r.__dict__) for r in summary.results]
        if session_id:  # finishing an upload counts as activity; touch before the job stops protecting it
            self.services.sessions.get(session_id, touch=True)
        self._update(job_id, status="completed", counts=counts, results=results, finished_at=datetime.now(UTC))

    def wait(self, timeout: float = 30.0) -> None:
        """Block until queued jobs finish (used by tests and the CLI-style flows)."""
        self._pool.submit(lambda: None).result(timeout=timeout)
