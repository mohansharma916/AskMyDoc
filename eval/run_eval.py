"""Full evaluation run: golden questions through the real pipeline, all metrics,
thresholds from eval/thresholds.yaml, report in eval/report.json and report.md.

    python -m eval.run_eval          # exits 1 if any threshold fails
    pytest eval/                     # same run, one test per threshold (used in CI)
"""

import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from askdocs.generate.llm import Usage
from askdocs.pipeline import PipelineOptions

from .build_golden import load_golden
from .harness import build_eval_services
from .metrics import recall_at_k, reciprocal_rank
from .scoring import (
    abstention_rates,
    check_thresholds,
    citation_pairs,
    load_thresholds,
    mean_or_none,
    percentile,
    report_markdown,
)

EVAL_DIR = Path(__file__).parent
REPORT_JSON = EVAL_DIR / "report.json"
REPORT_MD = EVAL_DIR / "report.md"


def has_llm_credentials(settings) -> bool:
    return settings.llm_provider != "anthropic" or bool(settings.llm_api_key or os.getenv("ANTHROPIC_API_KEY"))


def run_pipeline(services, items: list[dict], options: PipelineOptions | None = None) -> list[dict]:
    rows = []
    for item in items:
        result = services.pipeline.ask(item["question"], options=options)
        cited = {c.n for c in result.citations}
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "expected_answer": item["expected_answer"],
                "answerable": item["answerable"],
                "abstained": result.abstained,
                "abstain_reason": result.abstain_reason,
                "answer": result.answer,
                "context_texts": [c.text for c in result.contexts],
                "cited_texts": [c.text for n, c in enumerate(result.contexts, start=1) if n in cited],
                "recall_at_5": recall_at_k(item, result.ranked_chunk_ids, 5) if item["answerable"] else None,
                "reciprocal_rank": reciprocal_rank(item, result.ranked_chunk_ids, 10) if item["answerable"] else None,
                "latency_ms": result.latency_ms["total"],
                "usage": asdict(result.usage),
            }
        )
    return rows


def judge_rows(rows: list[dict], judge_model: str, api_key: str | None) -> None:
    """Adds citation_precision, faithfulness and answer_correctness to each row in place."""
    from . import ragas_metrics
    from .judge import CitationJudge

    judge = CitationJudge(judge_model, client=_anthropic_client(api_key))
    for row in rows:
        row["citation_pairs"] = row["citation_supported"] = None
        if row["answerable"] and not row["abstained"]:
            pairs = citation_pairs(row["answer"])
            verdicts = judge.judge(pairs, row["context_texts"])
            row["citation_pairs"], row["citation_supported"] = len(pairs), sum(verdicts)

    answered = [r for r in rows if r["answerable"] and not r["abstained"]]
    samples = [
        {
            "user_input": r["question"],
            "response": r["answer"],
            "retrieved_contexts": r["cited_texts"] or r["context_texts"],
            "reference": r["expected_answer"],
        }
        for r in answered
    ]
    for row, scores in zip(answered, ragas_metrics.score(samples, judge_model, api_key), strict=True):
        row.update(scores)
    for row in rows:
        if row["answerable"] and row["abstained"]:
            row["faithfulness"], row["answer_correctness"] = None, 0.0  # refusing an answerable question is wrong
        row.setdefault("faithfulness", None)
        row.setdefault("answer_correctness", None)


def _anthropic_client(api_key: str | None):
    import anthropic

    return anthropic.Anthropic(api_key=api_key or None)


def aggregate(rows: list[dict]) -> dict[str, float | None]:
    answerable = [r for r in rows if r["answerable"]]
    pairs = sum(r.get("citation_pairs") or 0 for r in rows)
    supported = sum(r.get("citation_supported") or 0 for r in rows)
    return {
        "recall_at_5": mean_or_none([r["recall_at_5"] for r in answerable]),
        "mrr_at_10": mean_or_none([r["reciprocal_rank"] for r in answerable]),
        "faithfulness": mean_or_none([r.get("faithfulness") for r in answerable]),
        "answer_correctness": mean_or_none([r.get("answer_correctness") for r in answerable]),
        "citation_precision": supported / pairs if pairs else None,
        **abstention_rates(rows),
        "latency_p95_ms": percentile([r["latency_ms"] for r in rows], 95),
    }


def run(services=None, items: list[dict] | None = None, judge: bool = True) -> dict:
    services = services or build_eval_services()
    s = services.settings
    items = items if items is not None else load_golden()
    rows = run_pipeline(services, items)
    judge_model = os.getenv("JUDGE_MODEL") or s.llm_model
    if judge:
        judge_rows(rows, judge_model, s.llm_api_key or None)
    metrics = aggregate(rows)
    results = check_thresholds(metrics, load_thresholds())
    usage = sum((Usage(**r["usage"]) for r in rows), Usage())
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "model": s.llm_model,
        "judge_model": judge_model,
        "prompt_version": s.prompt_version,
        "n_items": len(rows),
        "metrics": metrics,
        "results": results,
        "passed": all(r["passed"] for r in results.values()),
        "usage": asdict(usage),
        "items": rows,
    }


def write_report(report: dict) -> None:
    REPORT_JSON.write_text(json.dumps(report, indent=2, default=str))
    REPORT_MD.write_text(report_markdown(report))


def main() -> int:
    report = run()
    write_report(report)
    print(report_markdown(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
