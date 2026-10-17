from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from eval.judge import CitationJudge, CitationVerdicts, PairVerdict
from eval.run_eval import aggregate, has_llm_credentials, run
from eval.scoring import (
    abstention_rates,
    check_thresholds,
    citation_pairs,
    load_thresholds,
    mean_or_none,
    percentile,
    report_markdown,
)


def test_percentile_nearest_rank():
    assert percentile(list(range(1, 101)), 95) == 95
    assert percentile([5.0], 95) == 5.0
    assert percentile([], 95) == 0.0


def test_abstention_rates():
    rows = [
        {"answerable": True, "abstained": False},
        {"answerable": True, "abstained": True},
        {"answerable": False, "abstained": True},
        {"answerable": False, "abstained": True},
    ]
    assert abstention_rates(rows) == {"correct_abstention": 1.0, "false_abstention": 0.5}


def test_citation_pairs_dedupe_per_sentence():
    pairs = citation_pairs("Leave is 20 weeks [1][1][2]. It can be split in two [2].")
    assert pairs == [
        ("Leave is 20 weeks [1][1][2].", 1),
        ("Leave is 20 weeks [1][1][2].", 2),
        ("It can be split in two [2].", 2),
    ]


def test_mean_or_none():
    assert mean_or_none([1.0, None, float("nan"), 0.0]) == 0.5
    assert mean_or_none([None]) is None


def test_thresholds_file_and_check():
    thresholds = load_thresholds()
    assert thresholds["faithfulness"] == {"min": 0.85} and thresholds["latency_p95_ms"] == {"max": 4000}
    results = check_thresholds({"faithfulness": 0.9, "latency_p95_ms": 4500, "recall_at_5": None}, thresholds)
    assert results["faithfulness"]["passed"] and not results["latency_p95_ms"]["passed"]
    assert results["recall_at_5"] == {"value": None, "op": ">=", "threshold": 0.85, "passed": False}


def test_report_markdown():
    report = {
        "passed": False,
        "n_items": 50,
        "model": "m",
        "judge_model": "j",
        "prompt_version": "answer_v1",
        "results": {
            "faithfulness": {"value": 0.9, "op": ">=", "threshold": 0.85, "passed": True},
            "latency_p95_ms": {"value": 4500.0, "op": "<=", "threshold": 4000, "passed": False},
            "mrr_at_10": {"value": None, "op": ">=", "threshold": 0.7, "passed": False},
        },
        "usage": {"input_tokens": 10, "output_tokens": 2, "cost_usd": 0.5},
    }
    md = report_markdown(report)
    assert "❌" in md and "| faithfulness | 0.900 | >= 0.85 | pass |" in md
    assert "| latency_p95_ms | 4500 | <= 4000 | **FAIL** |" in md and "| mrr_at_10 | n/a |" in md
    assert "$0.5000" in md


def test_judge_maps_verdicts_and_skips_missing_excerpts():
    client = MagicMock()
    verdicts = CitationVerdicts(verdicts=[PairVerdict(pair=1, supported=True), PairVerdict(pair=2, supported=False)])
    client.messages.parse.return_value = SimpleNamespace(parsed_output=verdicts)
    judge = CitationJudge("judge-model", client=client)
    out = judge.judge([("A.", 1), ("B.", 9), ("C.", 2)], ["excerpt one", "excerpt two"])
    assert out == [True, False, False]
    prompt = client.messages.parse.call_args.kwargs["messages"][0]["content"]
    assert "Pair 1:\nSentence: A.\nExcerpt [1]: excerpt one" in prompt and "Pair 2:\nSentence: C." in prompt
    assert judge.judge([], []) == []
    assert judge.judge([("A.", 3)], ["x"]) == [False]


def test_run_without_judge_on_fake_stack(make_services):
    services = make_services()
    items = [
        {
            "id": "a",
            "question": "parental leave weeks",
            "expected_answer": "20 weeks",
            "answerable": True,
            "evidence": [{"chunk_ids": [c.chunk_id for c in services.indexer.list_documents()[1].chunks[:1]]}],
            "supporting_chunk_ids": [],
        },
        {"id": "u", "question": "dog policy pets", "expected_answer": "", "answerable": False, "evidence": []},
    ]
    services.pipeline.abstain_threshold = 0.5
    report = run(services, items, judge=False)
    assert report["n_items"] == 2 and report["metrics"]["recall_at_5"] == 1.0
    assert report["metrics"]["correct_abstention"] == 1.0 and report["metrics"]["false_abstention"] == 0.0
    assert report["metrics"]["faithfulness"] is None and not report["passed"]
    assert report["usage"]["input_tokens"] == 100


def test_aggregate_citation_precision():
    rows = [
        {"answerable": True, "abstained": False, "recall_at_5": 1, "reciprocal_rank": 1, "latency_ms": 10,
         "citation_pairs": 4, "citation_supported": 3, "faithfulness": 1.0, "answer_correctness": 0.5},
        {"answerable": True, "abstained": True, "recall_at_5": 0, "reciprocal_rank": 0, "latency_ms": 20,
         "citation_pairs": None, "citation_supported": None, "faithfulness": None, "answer_correctness": 0.0},
    ]  # fmt: skip
    m = aggregate(rows)
    assert m["citation_precision"] == 0.75 and m["answer_correctness"] == 0.25 and m["faithfulness"] == 1.0


@pytest.mark.parametrize(
    "provider, key, env, expected",
    [
        ("anthropic", "", None, False),
        ("anthropic", "k", None, True),
        ("anthropic", "", "e", True),
        ("ollama", "", None, True),
    ],
)
def test_has_llm_credentials(monkeypatch, provider, key, env, expected):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    if env:
        monkeypatch.setenv("ANTHROPIC_API_KEY", env)
    assert has_llm_credentials(SimpleNamespace(llm_provider=provider, llm_api_key=key)) is expected
