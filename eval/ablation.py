"""Ablation over the golden set.

    python -m eval.ablation                # retrieval metrics only (no LLM calls)
    python -m eval.ablation --generation   # also faithfulness, citation precision, correctness

Configurations: BM25 only, vector only, hybrid (RRF), hybrid + cross-encoder
rerank, and hybrid + rerank + citation validator. Writes eval/ablation.md.
"""

import argparse
import sys
from pathlib import Path

from askdocs.pipeline import PipelineOptions

from .build_golden import load_golden
from .harness import build_eval_services
from .metrics import retrieval_metrics

OUT = Path(__file__).parent / "ablation.md"

CONFIGS = [
    ("BM25 only", PipelineOptions(mode="bm25", rerank=False, validate_citations=False)),
    ("Vector only", PipelineOptions(mode="vector", rerank=False, validate_citations=False)),
    ("Hybrid (RRF)", PipelineOptions(mode="hybrid", rerank=False, validate_citations=False)),
    ("Hybrid + rerank", PipelineOptions(mode="hybrid", rerank=True, validate_citations=False)),
    ("Hybrid + rerank + citation validator", PipelineOptions(mode="hybrid", rerank=True, validate_citations=True)),
]


def rank_ids(services, question: str, options: PipelineOptions) -> list[str]:
    candidates = services.retriever.retrieve(question, k=services.settings.retrieve_k, mode=options.mode)
    if options.rerank:
        candidates = services.reranker.rerank(question, candidates)
    return [c.chunk_id for c in candidates]


def run(services=None, generation: bool = False) -> list[dict]:
    services = services or build_eval_services()
    golden = load_golden()
    answerable = [i for i in golden if i["answerable"]]
    rows, seen = [], {}
    for label, options in CONFIGS:
        key = (options.mode, options.rerank)  # the validator doesn't change retrieval
        if key not in seen:
            rankings = {i["id"]: rank_ids(services, i["question"], options) for i in answerable}
            seen[key] = retrieval_metrics(answerable, rankings)
        row = {"config": label, **seen[key]}
        if generation:
            row.update(_generation_metrics(services, golden, options))
        rows.append(row)
    return rows


def _generation_metrics(services, golden: list[dict], options: PipelineOptions) -> dict:
    import os

    from .run_eval import aggregate, judge_rows, run_pipeline

    results = run_pipeline(services, golden, options)
    judge_rows(results, os.getenv("JUDGE_MODEL", services.settings.llm_model), services.settings.llm_api_key or None)
    m = aggregate(results)
    return {k: m[k] for k in ("faithfulness", "citation_precision", "answer_correctness", "false_abstention")}


def _fmt(value) -> str:
    return "–" if value is None else f"{value:.3f}"


def to_markdown(rows: list[dict], n_items: int) -> str:
    generation = "faithfulness" in rows[0]
    cols = ["Recall@5", "MRR@10"] + (["Faithfulness", "Citation precision", "Correctness"] if generation else [])
    keys = ["recall_at_5", "mrr_at_10"] + (
        ["faithfulness", "citation_precision", "answer_correctness"] if generation else []
    )
    lines = [
        f"Ablation on {n_items} answerable golden questions (eval/corpus).",
        "",
        "| Configuration | " + " | ".join(cols) + " |",
        "| --- | " + " | ".join("---" for _ in cols) + " |",
    ]
    lines += [f"| {r['config']} | " + " | ".join(_fmt(r.get(k)) for k in keys) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation", action="store_true", help="Also run generation metrics (calls the LLM)")
    parser.add_argument("--no-write", action="store_true", help="Print only; don't update eval/ablation.md")
    args = parser.parse_args(argv)
    rows = run(generation=args.generation)
    table = to_markdown(rows, sum(i["answerable"] for i in load_golden()))
    print(table)
    if not args.no_write:
        OUT.write_text(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
