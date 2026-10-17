from unittest.mock import MagicMock

import numpy as np

from askdocs.rerank.cross_encoder import CrossEncoderReranker, rerank_text
from askdocs.retrieve.types import Candidate


def cand(cid, text, section=()):
    return Candidate(chunk_id=cid, doc_id="d", text=text, section_path=section, scores={"rrf": 0.01})


def test_rerank_sorts_by_score_and_keeps_earlier_scores():
    reranker = CrossEncoderReranker("any")
    model = MagicMock()
    model.predict.return_value = np.array([0.1, 0.9, 0.5])
    reranker.__dict__["_model"] = model

    out = reranker.rerank("q", [cand("a", "x"), cand("b", "y", ("Leave",)), cand("c", "z")])
    assert [c.chunk_id for c in out] == ["b", "c", "a"]
    assert out[0].scores == {"rrf": 0.01, "rerank": 0.9}
    pairs = model.predict.call_args.args[0]
    assert pairs[1] == ("q", "Leave\ny")
    assert model.predict.call_args.kwargs["activation_fn"] is not None
    assert reranker.rerank("q", []) == []


def test_rerank_text():
    assert rerank_text(cand("a", "body", ("A", "B"))) == "A > B\nbody"
    assert rerank_text(cand("a", "body")) == "body"
