import pytest
from sqlalchemy import func, select

from askdocs.ingest.chunker import TextChunk
from askdocs.ingest.indexer import Indexer, embedding_text, make_chunk_id, slugify
from askdocs.retrieve.bm25 import BM25Index
from askdocs.retrieve.vector import QdrantIndex, make_client
from askdocs.store.db import Database
from askdocs.store.models import Chunk

HANDBOOK = b"# Handbook\n\n## Leave\n\nEveryone gets 21 days.\n\n## Expenses\n\nReceipts within 30 days.\n"


@pytest.fixture
def indexer(embedder):
    db = Database("sqlite:///:memory:")
    vectors = QdrantIndex(make_client(":memory:"), "chunks", embedder.dim)
    return Indexer(db, vectors, embedder, BM25Index(), chunk_size=64, chunk_overlap=8)


def chunk_count(indexer):
    with indexer.db.session() as s:
        return s.scalar(select(func.count()).select_from(Chunk))


def test_ingest_writes_sqlite_qdrant_and_bm25(indexer):
    summary = indexer.ingest_files([("hr_handbook.md", HANDBOOK, "/docs/hr_handbook.md")])
    [result] = summary.results
    assert (result.doc_id, result.status, result.chunks) == ("hr-handbook", "indexed", 2)
    assert chunk_count(indexer) == 2
    assert indexer.vectors.count() == 2
    assert len(indexer.bm25) == 2

    [doc] = indexer.list_documents()
    assert doc.title == "Handbook" and doc.source_uri == "/docs/hr_handbook.md"
    assert [c.section_path for c in doc.chunks] == [["Handbook", "Leave"], ["Handbook", "Expenses"]]
    assert doc.chunks[0].chunk_id == make_chunk_id("hr-handbook", doc.content_hash, 0)


def test_unchanged_file_is_skipped_and_changed_file_replaced(indexer):
    indexer.ingest_bytes("hr_handbook.md", HANDBOOK)
    again = indexer.ingest_bytes("hr_handbook.md", HANDBOOK)
    assert again.status == "unchanged" and again.chunks == 2

    changed = indexer.ingest_bytes("hr_handbook.md", HANDBOOK + b"\n## Travel\n\nBook economy.\n")
    assert changed.status == "updated" and changed.chunks == 3
    assert chunk_count(indexer) == 3
    assert indexer.vectors.count() == 3  # old vectors deleted, not duplicated


def test_same_stem_different_file_gets_distinct_id(indexer):
    a = indexer.ingest_bytes("policy.md", b"# A\n\nText a.")
    b = indexer.ingest_bytes("policy.txt", b"Text b.")
    assert a.doc_id == "policy" and b.doc_id == "policy-txt"


def test_failures_are_recorded(indexer):
    summary = indexer.ingest_files([("empty.md", b"", "x"), ("pic.png", b"..", "y"), ("ok.txt", b"Hi.", "z")])
    assert [r.status for r in summary.results] == ["failed", "failed", "indexed"]
    assert summary.count("failed") == 2 and summary.chunks == 1
    assert "No extractable text" in summary.results[0].error


def test_ingest_path_walks_supported_files(indexer, tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.md").write_bytes(HANDBOOK)
    (tmp_path / "sub" / "b.txt").write_text("Plain text policy.")
    (tmp_path / "skip.png").write_bytes(b"x")
    summary = indexer.ingest_path(tmp_path)
    assert sorted(r.file_name for r in summary.results) == ["a.md", "b.txt"]
    assert indexer.ingest_path(tmp_path / "a.md").results[0].status == "unchanged"


def test_delete(indexer):
    indexer.ingest_bytes("a.md", HANDBOOK)
    assert indexer.delete("a") is True
    assert chunk_count(indexer) == 0 and indexer.vectors.count() == 0
    assert indexer.delete("a") is False


def test_helpers():
    assert slugify("HR Handbook (2026)!") == "hr-handbook-2026"
    assert slugify("!!!") == "document"
    chunk = TextChunk("Body.", 1, ("A", "B"), 2, 0)
    assert embedding_text("Title", chunk) == "Title\nA > B\n\nBody."
    assert embedding_text("Title", TextChunk("Body.", 1, (), 2, 0)) == "Title\n\nBody."
