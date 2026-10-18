"""Anonymous browser sessions.

Each browser gets a random session id. Documents uploaded in a session are
visible only to it, and everything the session created (documents, chunks,
Qdrant points, BM25 entries, uploaded files and query traces) is deleted after
``ttl_s`` seconds without activity.
"""

import logging
import secrets
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select

from .ingest.indexer import Indexer, session_tag
from .store.db import Database
from .store.models import BrowserSession, Document, Trace

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    expires_at: datetime
    ttl_s: int


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # SQLite returns naive UTC datetimes


class SessionStore:
    def __init__(self, db: Database, indexer: Indexer, upload_root: Path, ttl_s: int = 300):
        self.db = db
        self.indexer = indexer
        self.upload_root = upload_root
        self.ttl_s = ttl_s

    def upload_dir(self, session_id: str) -> Path:
        return self.upload_root / session_tag(session_id)

    def _info(self, row: BrowserSession) -> SessionInfo:
        return SessionInfo(row.session_id, _aware(row.last_seen_at) + timedelta(seconds=self.ttl_s), self.ttl_s)

    def _expired(self, row: BrowserSession, now: datetime) -> bool:
        return _aware(row.last_seen_at) + timedelta(seconds=self.ttl_s) <= now

    def create(self) -> SessionInfo:
        row = BrowserSession(session_id=secrets.token_urlsafe(24))
        with self.db.session() as s:
            s.add(row)
        return self._info(row)

    def get(self, session_id: str, touch: bool = False) -> SessionInfo | None:
        """The live session, optionally marking activity; None if unknown or expired (and then purged)."""
        now = datetime.now(UTC)
        with self.db.session() as s:
            row = s.get(BrowserSession, session_id)
            if row is None:
                return None
            if not self._expired(row, now):
                if touch:
                    row.last_seen_at = now
                return self._info(row)
        self.purge(session_id)
        return None

    def owns(self, session_id: str | None, doc_id: str) -> bool:
        if not session_id:
            return False
        with self.db.session() as s:
            doc = s.get(Document, doc_id)
            return doc is not None and doc.session_id == session_id

    def purge(self, session_id: str) -> int:
        """Delete everything the session created; returns how many documents were removed."""
        with self.db.session() as s:
            doc_ids = list(s.scalars(select(Document.doc_id).where(Document.session_id == session_id)))
        removed = self.indexer.delete_many(doc_ids) if doc_ids else 0
        with self.db.session() as s:
            s.execute(delete(Trace).where(Trace.session_id == session_id))  # feedback cascades
            s.execute(delete(BrowserSession).where(BrowserSession.session_id == session_id))
        shutil.rmtree(self.upload_dir(session_id), ignore_errors=True)
        log.info("purged session %s: %d documents", session_tag(session_id), removed)
        return removed

    def sweep(self, keep: set[str] = frozenset()) -> list[str]:
        """Purge every expired session except those in `keep` (e.g. with an ingest still running)."""
        now = datetime.now(UTC)
        with self.db.session() as s:
            expired = [r.session_id for r in s.scalars(select(BrowserSession)) if self._expired(r, now)]
        expired = [sid for sid in expired if sid not in keep]
        for sid in expired:
            self.purge(sid)
        return expired
