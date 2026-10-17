from .types import Candidate

RRF_K = 60


def reciprocal_rank_fusion(ranked_lists: list[list[Candidate]], k: int = RRF_K, top_n: int = 20) -> list[Candidate]:
    """Fuse rankings by score = sum(1 / (k + rank)), rank starting at 1.

    Scores from each list (bm25, vector, ...) are merged onto one Candidate per
    chunk so later stages can show where a result came from.
    """
    fused: dict[str, Candidate] = {}
    rrf: dict[str, float] = {}
    for ranking in ranked_lists:
        for rank, cand in enumerate(ranking, start=1):
            if cand.chunk_id not in fused:
                fused[cand.chunk_id] = Candidate(**{**cand.__dict__, "scores": {}})
            fused[cand.chunk_id].scores.update(cand.scores)
            rrf[cand.chunk_id] = rrf.get(cand.chunk_id, 0.0) + 1.0 / (k + rank)

    order = sorted(fused, key=lambda cid: rrf[cid], reverse=True)[:top_n]
    for cid in order:
        fused[cid].scores["rrf"] = rrf[cid]
    return [fused[cid] for cid in order]
