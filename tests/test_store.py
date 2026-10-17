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
