"""Tune ABSTAIN_THRESHOLD on the golden set (retrieval + rerank only, no LLM calls).

    python -m eval.tune_threshold [--max-false-abstention 0.0]

For each candidate threshold it reports how many unanswerable questions are
stopped before generation and how many answerable ones would be wrongly
refused, then recommends the lowest threshold that stops the most
unanswerable questions within the false-abstention budget. The LLM's own
NOT_FOUND reply still catches unanswerable questions that pass this filter.
"""

import argparse
import sys

from .build_golden import load_golden
from .harness import build_eval_services


def best_scores(services, items: list[dict]) -> dict[str, float]:
    k = services.settings.retrieve_k
    scores = {}
    for item in items:
        ranked = services.reranker.rerank(item["question"], services.retriever.retrieve(item["question"], k=k))
        scores[item["id"]] = ranked[0].scores["rerank"] if ranked else 0.0
    return scores


def sweep(items: list[dict], scores: dict[str, float]) -> list[dict]:
    answerable = [scores[i["id"]] for i in items if i["answerable"]]
    unanswerable = [scores[i["id"]] for i in items if not i["answerable"]]
    # Midpoints between neighbouring scores, so a threshold never sits exactly on a sample.
    ordered = sorted(set(scores.values()))
    candidates = [0.0] + [round((a + b) / 2, 4) for a, b in zip(ordered, ordered[1:], strict=False)]
    rows = []
    for t in candidates:
        rows.append(
            {
                "threshold": t,
                "correct_abstention": sum(s < t for s in unanswerable) / max(len(unanswerable), 1),
                "false_abstention": sum(s < t for s in answerable) / max(len(answerable), 1),
            }
        )
    return rows


def recommend(rows: list[dict], max_false_abstention: float) -> dict:
    ok = [r for r in rows if r["false_abstention"] <= max_false_abstention]
    return max(ok, key=lambda r: (r["correct_abstention"], -r["threshold"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-false-abstention", type=float, default=0.0)
    args = parser.parse_args(argv)

    items = load_golden()
    scores = best_scores(build_eval_services(), items)
    print("id      answerable  best_rerank")
    for item in sorted(items, key=lambda i: scores[i["id"]]):
        print(f"{item['id']}  {item['answerable']!s:<10}  {scores[item['id']]:.3f}")

    rows = sweep(items, scores)
    best = recommend(rows, args.max_false_abstention)
    print(
        f"\nRecommended ABSTAIN_THRESHOLD={best['threshold']:.4f}: stops "
        f"{best['correct_abstention']:.0%} of unanswerable questions before the LLM, "
        f"false abstention {best['false_abstention']:.0%} (budget {args.max_false_abstention:.0%})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
