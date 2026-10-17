"""Retrieval ablation over the golden set.

    python -m eval.ablation            # prints the table and writes eval/ablation.md

Configurations: BM25 only, vector only, hybrid (RRF), hybrid + cross-encoder rerank.
"""

import argparse
import sys
from pathlib import Path

from .build_golden import load_golden
from .harness import build_eval_services
from .metrics import retrieval_metrics

OUT = Path(__file__).parent / "ablation.md"

CONFIGS = [
    ("BM25 only", "bm25", False),
    ("Vector only", "vector", False),
    ("Hybrid (RRF)", "hybrid", False),
    ("Hybrid + rerank", "hybrid", True),
]


def rank_ids(services, question: str, mode: str, rerank: bool) -> list[str]:
    s = services.settings
    candidates = services.retriever.retrieve(question, k=s.retrieve_k, mode=mode)
    if rerank:
        candidates = services.reranker.rerank(question, candidates)
    return [c.chunk_id for c in candidates]


def run(services=None) -> list[dict]:
    services = services or build_eval_services()
    items = [i for i in load_golden() if i["answerable"]]
    rows = []
    for label, mode, rerank in CONFIGS:
        rankings = {i["id"]: rank_ids(services, i["question"], mode, rerank) for i in items}
        rows.append({"config": label, **retrieval_metrics(items, rankings)})
    return rows


def to_markdown(rows: list[dict], n_items: int) -> str:
    lines = [
        f"Retrieval ablation on {n_items} answerable golden questions (eval/corpus).",
        "",
        "| Configuration | Recall@5 | MRR@10 |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {r['config']} | {r['recall_at_5']:.3f} | {r['mrr_at_10']:.3f} |" for r in rows]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="Print only; don't update eval/ablation.md")
    args = parser.parse_args(argv)
    rows = run()
    table = to_markdown(rows, sum(i["answerable"] for i in load_golden()))
    print(table)
    if not args.no_write:
        OUT.write_text(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
