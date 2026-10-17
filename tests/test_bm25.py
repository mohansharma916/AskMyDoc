from askdocs.retrieve.bm25 import BM25Index, BM25Row, tokenize
from askdocs.store.db import Database
from askdocs.store.models import Chunk, Document


def test_tokenize_lowercases_and_drops_stopwords():
    assert tokenize("How many PTO-days do I get?") == ["many", "pto", "days", "get"]


def test_build_empty_and_rows():
    index = BM25Index()
    index.build([])
    assert len(index) == 0
    index.build([BM25Row("c1", "d1", "parental leave")], fingerprint=(1,))
    assert len(index) == 1 and index.fingerprint == (1,)


def test_rebuild_from_db_and_freshness():
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        doc = Document(doc_id="d1", file_name="a.md", source_uri="a.md", content_hash="h", title="A")
        doc.chunks = [Chunk(chunk_id="c1", text="leave", section_path=["HR"], token_count=1, position=0)]
        s.add(doc)

    index = BM25Index()
    index.ensure_fresh(db)
    assert len(index) == 1
    assert index._rows[0].text == "HR leave"
    fingerprint = index.fingerprint

    index.ensure_fresh(db)  # unchanged: no rebuild
    assert index.fingerprint == fingerprint

    with db.session() as s:
        s.add(Chunk(chunk_id="c2", doc_id="d1", text="expenses", section_path=[], token_count=1, position=1))
    index.ensure_fresh(db)
    assert len(index) == 2
