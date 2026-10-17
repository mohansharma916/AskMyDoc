"""In-process BM25 keyword index (rank_bm25), rebuilt from the chunk table.

SQLite is the source of truth, so the index is cheap to rebuild whenever the
chunk table changes (detected with a fingerprint), including changes made by
another process such as the ingestion CLI.
"""

import re
import threading
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import func, select

from ..store.db import Database
from ..store.models import Chunk, Document

_TOKEN = re.compile(r"\w+", re.UNICODE)
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i in is it its of on or "
    "that the their there this to was what when where which who why will with you your".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


@dataclass(frozen=True)
class BM25Row:
    chunk_id: str
    doc_id: str
    text: str


class BM25Index:
    def __init__(self):
        self._lock = threading.Lock()
        self._bm25: BM25Okapi | None = None
        self._rows: list[BM25Row] = []
        self.fingerprint: tuple | None = None

    def __len__(self) -> int:
        return len(self._rows)

    def build(self, rows: list[BM25Row], fingerprint: tuple | None = None) -> None:
        corpus = [tokenize(r.text) for r in rows]
        bm25 = BM25Okapi(corpus) if rows else None
        with self._lock:
            self._rows, self._bm25, self.fingerprint = rows, bm25, fingerprint

    @staticmethod
    def db_fingerprint(db: Database) -> tuple:
        with db.session() as s:
            chunks = s.scalar(select(func.count()).select_from(Chunk))
            docs, latest = s.execute(select(func.count(), func.max(Document.ingested_at))).one()
        return chunks, docs, str(latest)

    def rebuild_from_db(self, db: Database) -> None:
        fingerprint = self.db_fingerprint(db)
        with db.session() as s:
            result = s.execute(select(Chunk.chunk_id, Chunk.doc_id, Chunk.section_path, Chunk.text))
            # Section headings are indexed with the text so "parental leave" matches its section.
            rows = [BM25Row(cid, did, " ".join([*path, text])) for cid, did, path, text in result]
        self.build(rows, fingerprint)

    def ensure_fresh(self, db: Database) -> None:
        if self.fingerprint != self.db_fingerprint(db):
            self.rebuild_from_db(db)
