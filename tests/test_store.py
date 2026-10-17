from sqlalchemy import select

from askdocs.store.db import Database
from askdocs.store.models import Chunk, Document


def _doc(doc_id="hr-handbook"):
    return Document(doc_id=doc_id, file_name="hr.md", source_uri="/x/hr.md", content_hash="abc", title="HR")


def test_document_with_chunks_round_trip(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'sub' / 'a.db'}")
    with db.session() as s:
        doc = _doc()
        doc.chunks = [
            Chunk(chunk_id="c1", text="one", page=1, section_path=["A", "B"], token_count=1, position=0),
            Chunk(chunk_id="c2", text="two", page=2, section_path=[], token_count=1, position=1),
        ]
        s.add(doc)

    with db.session() as s:
        loaded = s.get(Document, "hr-handbook")
        assert [c.chunk_id for c in loaded.chunks] == ["c1", "c2"]
        assert loaded.chunks[0].section_path == ["A", "B"]
        assert loaded.ingested_at is not None


def test_deleting_document_cascades_to_chunks():
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        doc = _doc()
        doc.chunks = [Chunk(chunk_id="c1", text="t", page=None, section_path=[], token_count=1, position=0)]
        s.add(doc)
    with db.session() as s:
        s.delete(s.get(Document, "hr-handbook"))
    with db.session() as s:
        assert s.scalars(select(Chunk)).all() == []


def test_ping():
    assert Database("sqlite:///:memory:").ping()


def test_in_memory_database_is_shared_across_threads():
    from concurrent.futures import ThreadPoolExecutor

    db = Database("sqlite:///:memory:")
    with db.session() as s:
        s.add(_doc())
    with ThreadPoolExecutor(1) as pool:
        assert pool.submit(lambda: db.session().__enter__().get(Document, "hr-handbook")).result() is not None


def test_missing_nullable_columns_are_added_to_existing_tables(tmp_path):
    import sqlite3

    from askdocs.store.db import add_missing_columns

    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE traces (query_id VARCHAR(40) PRIMARY KEY, question TEXT, answer TEXT)")
    con.commit()
    con.close()

    db = Database(f"sqlite:///{path}")  # runs the migration on open
    columns = {row[1] for row in sqlite3.connect(path).execute("PRAGMA table_info(traces)")}
    assert {"otel_trace_id", "model", "prompt_version"} <= columns
    assert add_missing_columns(db.engine) == []  # idempotent
