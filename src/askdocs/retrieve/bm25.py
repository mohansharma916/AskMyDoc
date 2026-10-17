"""In-process BM25 keyword index (rank_bm25), rebuilt from the chunk table.

SQLite is the source of truth, so the index is cheap to rebuild whenever the
chunk table changes (detected with a fingerprint), including changes made by
another process such as the ingestion CLI.
"""

import re
import threading

import numpy as np
from rank_bm25 import BM25Plus
from sqlalchemy import func, select

from ..store.db import Database
from ..store.models import Chunk, Document
from .types import Candidate

_TOKEN = re.compile(r"\w+", re.UNICODE)
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i in is it its of on or "
    "that the their there this to was what when where which who why will with you your".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


class BM25Index:
    def __init__(self):
        self._lock = threading.Lock()
        self._bm25: BM25Plus | None = None
        self._rows: list[Candidate] = []
        self.fingerprint: tuple | None = None

    def __len__(self) -> int:
        return len(self._rows)

    def build(self, rows: list[Candidate], fingerprint: tuple | None = None) -> None:
        # Section headings are indexed with the text so "parental leave" matches its section.
        corpus = [tokenize(" ".join([*r.section_path, r.text])) for r in rows]
        # BM25+ keeps IDF positive, so terms common in a small corpus still score (Okapi goes <= 0).
        bm25 = BM25Plus(corpus) if rows else None
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
        query = select(Chunk, Document.file_name, Document.title).join(Document).order_by(Chunk.chunk_id)
        with db.session() as s:
            rows = [
                Candidate(
                    chunk_id=c.chunk_id,
                    doc_id=c.doc_id,
                    text=c.text,
                    file_name=file_name,
                    title=title,
                    page=c.page,
                    section_path=tuple(c.section_path),
                )
                for c, file_name, title in s.execute(query)
            ]
        self.build(rows, fingerprint)

    def ensure_fresh(self, db: Database) -> None:
        if self.fingerprint != self.db_fingerprint(db):
            self.rebuild_from_db(db)

    def search(self, query: str, k: int = 20, doc_ids: list[str] | None = None) -> list[Candidate]:
        """Top-k chunks by BM25 score; chunks sharing no query term are never returned."""
        tokens = tokenize(query)
        with self._lock:
            bm25, rows = self._bm25, self._rows
        if bm25 is None or not tokens:
            return []
        scores = bm25.get_scores(tokens)
        # BM25+ gives every chunk a floor score, so require at least one shared query term.
        matched = np.array([any(t in bm25.doc_freqs[i] for t in tokens) for i in range(len(rows))])
        if doc_ids is not None:
            allowed = set(doc_ids)
            matched &= np.array([r.doc_id in allowed for r in rows])
        scores = np.where(matched, scores, -np.inf)
        top = [i for i in np.argsort(-scores, kind="stable")[:k] if matched[i]]
        return [Candidate(**{**rows[i].__dict__, "scores": {"bm25": float(scores[i])}}) for i in top]
