import pytest

from askdocs.retrieve.bm25 import BM25Index, tokenize
from askdocs.retrieve.types import Candidate
from askdocs.store.db import Database
from askdocs.store.models import Chunk, Document


def test_tokenize_lowercases_and_drops_stopwords():
    assert tokenize("How many PTO-days do I get?") == ["many", "pto", "days", "get"]


def row(cid, doc, text, section=()):
    return Candidate(chunk_id=cid, doc_id=doc, text=text, section_path=section)


@pytest.fixture
def index():
    idx = BM25Index()
    idx.build(
        [
            row("c1", "hr", "Primary caregivers receive 20 weeks of parental leave.", ("Leave",)),
            row("c2", "hr", "Employees accrue 21 days of paid time off.", ("PTO",)),
            row("c3", "it", "Report lost laptops within 24 hours.", ("Devices",)),
            row("c4", "travel", "Economy class for flights under six hours."),
        ]
    )
    return idx


def test_search_ranks_by_bm25_and_skips_non_matches(index):
    hits = index.search("parental leave weeks")
    assert hits[0].chunk_id == "c1"
    assert all(h.scores["bm25"] > 0 for h in hits)
    assert {h.chunk_id for h in hits} == {"c1"}  # no other chunk shares a term


def test_section_headings_are_searchable(index):
    assert index.search("devices")[0].chunk_id == "c3"


def test_doc_filter_and_k(index):
    assert index.search("leave days hours", doc_ids=["it"])[0].doc_id == "it"
    assert len(index.search("leave days hours flights", k=2)) == 2
    assert index.search("leave", doc_ids=[]) == []


def test_empty_index_and_stopword_query(index):
    assert BM25Index().search("anything") == []
    assert index.search("the of and") == []


def test_build_empty_and_rows():
    idx = BM25Index()
    idx.build([])
    assert len(idx) == 0
    idx.build([row("c1", "d1", "parental leave")], fingerprint=(1,))
    assert len(idx) == 1 and idx.fingerprint == (1,)


def test_rebuild_from_db_and_freshness():
    db = Database("sqlite:///:memory:")
    with db.session() as s:
        doc = Document(doc_id="d1", file_name="a.md", source_uri="a.md", content_hash="h", title="A")
        doc.chunks = [Chunk(chunk_id="c1", text="leave", section_path=["HR"], token_count=1, position=0)]
        doc.chunks[0].page = 2
        s.add(doc)

    idx = BM25Index()
    idx.ensure_fresh(db)
    [hit] = idx.search("hr leave")
    assert (hit.file_name, hit.title, hit.page, hit.section_path) == ("a.md", "A", 2, ("HR",))
    fingerprint = idx.fingerprint

    idx.ensure_fresh(db)  # unchanged: no rebuild
    assert idx.fingerprint == fingerprint

    with db.session() as s:
        s.add(Chunk(chunk_id="c2", doc_id="d1", text="expenses", section_path=[], token_count=1, position=1))
    idx.ensure_fresh(db)
    assert len(idx) == 2
