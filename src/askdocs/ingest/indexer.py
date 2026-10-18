"""Ingestion job: parse -> chunk -> embed -> write SQLite, Qdrant and BM25.

Files are keyed by content hash: unchanged files are skipped, changed files
are deleted and re-inserted, so re-ingesting never duplicates chunks.
"""

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy import or_, select

from ..retrieve.bm25 import BM25Index
from ..retrieve.embeddings import Embedder
from ..retrieve.vector import QdrantIndex, VectorPoint
from ..store.db import Database
from ..store.models import Chunk, Document
from .chunker import TextChunk, chunk_blocks
from .parsers import SUPPORTED_EXTENSIONS, parse_bytes

log = logging.getLogger(__name__)

CHUNK_NAMESPACE = uuid.UUID("6f1c2b1e-7d3a-4c55-9a51-0b8f5d1e2a77")


@dataclass
class IngestResult:
    doc_id: str
    file_name: str
    status: Literal["indexed", "updated", "unchanged", "failed"]
    chunks: int = 0
    error: str | None = None


@dataclass
class IngestSummary:
    results: list[IngestResult] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(r.status == status for r in self.results)

    @property
    def chunks(self) -> int:
        return sum(r.chunks for r in self.results if r.status in ("indexed", "updated"))


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "document"


def session_tag(session_id: str) -> str:
    """Short, non-reversible label for a session, safe to use in doc ids and folder names."""
    return hashlib.sha256(session_id.encode()).hexdigest()[:12]


def make_chunk_id(doc_id: str, content_hash: str, position: int) -> str:
    """Deterministic UUID: the same file content always yields the same chunk ids."""
    return str(uuid.uuid5(CHUNK_NAMESPACE, f"{doc_id}:{content_hash}:{position}"))


def embedding_text(title: str, chunk: TextChunk) -> str:
    """Prefix each chunk with its document title and section path before embedding."""
    header = [title]
    if chunk.section_path:
        header.append(" > ".join(chunk.section_path))
    return "\n".join(header) + "\n\n" + chunk.text


class Indexer:
    def __init__(
        self,
        db: Database,
        vectors: QdrantIndex,
        embedder: Embedder,
        bm25: BM25Index,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ):
        self.db = db
        self.vectors = vectors
        self.embedder = embedder
        self.bm25 = bm25
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _doc_id_for(self, file_name: str, source_uri: str, session_id: str | None = None) -> str:
        """Slug of the file stem (plus a session tag for session uploads, so two browsers
        uploading report.pdf never collide); disambiguated if another file already owns it."""
        base = slugify(Path(file_name).stem)
        if session_id:
            base = f"{base}--{session_tag(session_id)}"
        with self.db.session() as s:
            existing = s.get(Document, base)
            if existing is None or existing.file_name == file_name:
                return base
        suffix = slugify(Path(file_name).suffix) or hashlib.sha1(source_uri.encode()).hexdigest()[:6]
        return f"{base}-{suffix}"

    def ingest_bytes(
        self, file_name: str, data: bytes, source_uri: str | None = None, session_id: str | None = None
    ) -> IngestResult:
        source_uri = source_uri or file_name
        doc_id = self._doc_id_for(file_name, source_uri, session_id)
        content_hash = hashlib.sha256(data).hexdigest()

        with self.db.session() as s:
            existing = s.get(Document, doc_id)
            if existing is not None and existing.content_hash == content_hash:
                return IngestResult(doc_id, file_name, "unchanged", len(existing.chunks))

        parsed = parse_bytes(file_name, data)
        chunks = chunk_blocks(parsed.blocks, self.chunk_size, self.chunk_overlap)
        if not chunks:
            raise ValueError(f"No extractable text in '{file_name}'")
        vectors = self.embedder.embed_documents([embedding_text(parsed.title, c) for c in chunks])

        status = "updated" if existing is not None else "indexed"
        chunk_ids = [make_chunk_id(doc_id, content_hash, c.position) for c in chunks]
        with self.db.session() as s:
            if existing is not None:  # delete-then-insert for changed files
                s.delete(s.get(Document, doc_id))
                s.flush()
                self.vectors.delete_document(doc_id)
            doc = Document(
                doc_id=doc_id,
                session_id=session_id,
                file_name=file_name,
                source_uri=source_uri,
                content_hash=content_hash,
                title=parsed.title,
            )
            doc.chunks = [
                Chunk(
                    chunk_id=cid,
                    text=c.text,
                    page=c.page,
                    section_path=list(c.section_path),
                    token_count=c.token_count,
                    position=c.position,
                )
                for cid, c in zip(chunk_ids, chunks, strict=True)
            ]
            s.add(doc)
            s.flush()  # surface DB errors before touching Qdrant
            self.vectors.upsert(
                [
                    VectorPoint(
                        cid,
                        vector,
                        {
                            "doc_id": doc_id,
                            "session_id": session_id,
                            "file_name": file_name,
                            "title": parsed.title,
                            "page": c.page,
                            "section_path": list(c.section_path),
                            "position": c.position,
                            "text": c.text,
                        },
                    )
                    for cid, vector, c in zip(chunk_ids, vectors, chunks, strict=True)
                ]
            )
        log.info("%s %s: %d chunks", status, file_name, len(chunks))
        return IngestResult(doc_id, file_name, status, len(chunks))

    def ingest_path(self, path: Path) -> IngestSummary:
        """Index one file or every supported file under a folder, then rebuild BM25 once."""
        if path.is_file():
            files = [path]
        else:
            files = sorted(p for p in path.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS)
        return self.ingest_files((f.name, f.read_bytes(), str(f.resolve())) for f in files if f.is_file())

    def ingest_files(self, files, session_id: str | None = None) -> IngestSummary:
        """Ingest (file_name, data, source_uri) triples; failures are recorded, not raised.
        With a session_id the documents belong to that browser session; otherwise they are shared."""
        summary = IngestSummary()
        for file_name, data, source_uri in files:
            try:
                summary.results.append(self.ingest_bytes(file_name, data, source_uri, session_id))
            except Exception as exc:
                log.warning("failed %s: %s", file_name, exc)
                summary.results.append(IngestResult("", file_name, "failed", error=str(exc)))
        self.bm25.rebuild_from_db(self.db)
        log.info(
            "ingest done: %d indexed, %d updated, %d unchanged, %d failed, %d chunks written",
            summary.count("indexed"),
            summary.count("updated"),
            summary.count("unchanged"),
            summary.count("failed"),
            summary.chunks,
        )
        return summary

    def delete(self, doc_id: str) -> bool:
        return self.delete_many([doc_id]) == 1

    def delete_many(self, doc_ids: list[str]) -> int:
        """Delete documents from SQLite (chunks cascade), Qdrant and BM25; returns how many existed."""
        with self.db.session() as s:
            docs = s.scalars(select(Document).where(Document.doc_id.in_(doc_ids))).all()
            for doc in docs:
                s.delete(doc)
        if docs:
            self.vectors.delete_documents([d.doc_id for d in docs])
            self.bm25.rebuild_from_db(self.db)
        return len(docs)

    @staticmethod
    def visible(session_id: str | None):
        """SQL condition: shared documents plus the given session's own uploads."""
        shared = Document.session_id.is_(None)
        return or_(shared, Document.session_id == session_id) if session_id else shared

    def visible_doc_ids(self, session_id: str | None) -> list[str]:
        with self.db.session() as s:
            return list(s.scalars(select(Document.doc_id).where(self.visible(session_id))))

    def list_documents(self, session_id: str | None = None) -> list[Document]:
        with self.db.session() as s:
            query = select(Document).where(self.visible(session_id)).order_by(Document.file_name)
            docs = s.scalars(query).all()
            for d in docs:
                _ = d.chunks  # load before the session closes
            return list(docs)
