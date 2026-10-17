import pytest

from eval.ablation import to_markdown
from eval.metrics import recall_at_k, reciprocal_rank, retrieval_metrics

SINGLE = {"id": "s", "answerable": True, "evidence": [{"chunk_ids": ["a", "a2"]}], "supporting_chunk_ids": ["a"]}
MULTI = {"id": "m", "answerable": True, "evidence": [{"chunk_ids": ["a"]}, {"chunk_ids": ["b"]}]}
UNANS = {"id": "u", "answerable": False, "evidence": [], "supporting_chunk_ids": []}


def test_recall_any_chunk_in_group_counts():
    assert recall_at_k(SINGLE, ["x", "a2"], k=5) == 1.0
    assert recall_at_k(SINGLE, ["x"] * 5 + ["a"], k=5) == 0.0


def test_recall_multi_chunk_is_fractional():
    assert recall_at_k(MULTI, ["a", "x"], k=5) == 0.5
    assert recall_at_k(MULTI, ["b", "a"], k=5) == 1.0


def test_recall_falls_back_to_supporting_ids():
    item = {"supporting_chunk_ids": ["a", "b"]}
    assert recall_at_k(item, ["a"]) == 0.5
    assert recall_at_k({"supporting_chunk_ids": []}, ["a"]) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank(MULTI, ["x", "b"]) == 0.5
    assert reciprocal_rank(MULTI, ["x"] * 10 + ["a"]) == 0.0


def test_retrieval_metrics_ignores_unanswerable():
    m = retrieval_metrics([SINGLE, MULTI, UNANS], {"s": ["a"], "m": ["x", "a"], "u": []})
    assert m["recall_at_5"] == pytest.approx(0.75)
    assert m["mrr_at_10"] == pytest.approx(0.75)


def test_markdown_table():
    md = to_markdown([{"config": "BM25 only", "recall_at_5": 0.9, "mrr_at_10": 0.8}], 40)
    assert "| BM25 only | 0.900 | 0.800 |" in md and "40 answerable" in md
    row = {"config": "Full", "recall_at_5": 1, "mrr_at_10": 1, "faithfulness": 0.9, "citation_precision": None}
    md = to_markdown([row], 40)
    assert "Citation precision" in md and "| Full | 1.000 | 1.000 | 0.900 | – | – |" in md


def test_ablation_run_on_fake_stack(make_services, monkeypatch):
    from eval import ablation

    services = make_services()
    leave = services.indexer.list_documents()[1].chunks[0].chunk_id
    golden = [{"id": "a", "question": "parental leave weeks", "answerable": True, "evidence": [{"chunk_ids": [leave]}]}]
    monkeypatch.setattr(ablation, "load_golden", lambda: golden)
    rows = ablation.run(services)
    assert [r["config"] for r in rows][-1] == "Hybrid + rerank + citation validator"
    assert all(r["recall_at_5"] == 1.0 for r in rows)
