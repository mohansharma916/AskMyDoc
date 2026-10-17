"""Retrieval metrics over golden items.

A golden item lists evidence groups; each group is satisfied by any of its
chunk ids (overlapping chunks can both contain a quote). Multi-chunk items
need every group retrieved for full recall.
"""

from statistics import mean


def _groups(item: dict) -> list[set[str]]:
    if item.get("evidence"):
        return [set(e["chunk_ids"]) for e in item["evidence"]]
    return [{cid} for cid in item["supporting_chunk_ids"]]


def recall_at_k(item: dict, ranked_ids: list[str], k: int = 5) -> float:
    groups = _groups(item)
    if not groups:
        return 0.0
    top = set(ranked_ids[:k])
    return sum(bool(g & top) for g in groups) / len(groups)


def reciprocal_rank(item: dict, ranked_ids: list[str], k: int = 10) -> float:
    relevant = set().union(*_groups(item)) if _groups(item) else set()
    for rank, cid in enumerate(ranked_ids[:k], start=1):
        if cid in relevant:
            return 1.0 / rank
    return 0.0


def retrieval_metrics(items: list[dict], rankings: dict[str, list[str]]) -> dict[str, float]:
    """Mean Recall@5 and MRR@10 over answerable items; `rankings` maps item id -> ranked chunk ids."""
    answerable = [i for i in items if i["answerable"]]
    return {
        "recall_at_5": mean(recall_at_k(i, rankings[i["id"]], 5) for i in answerable),
        "mrr_at_10": mean(reciprocal_rank(i, rankings[i["id"]], 10) for i in answerable),
    }
