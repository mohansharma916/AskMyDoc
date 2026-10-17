from unittest.mock import MagicMock

import numpy as np

from askdocs.retrieve.embeddings import SentenceTransformerEmbedder


def test_query_prefix_only_applied_to_queries():
    emb = SentenceTransformerEmbedder("any-model", query_prefix="Q: ")
    model = MagicMock()
    model.encode.side_effect = lambda x, **kw: np.zeros((len(x), 3)) if isinstance(x, list) else np.zeros(3)
    emb.__dict__["_model"] = model  # bypass the cached model download

    assert emb.embed_documents(["a", "b"]) == [[0.0] * 3, [0.0] * 3]
    assert model.encode.call_args.args[0] == ["a", "b"]
    assert emb.embed_query("hello") == [0.0] * 3
    assert model.encode.call_args.args[0] == "Q: hello"
    assert model.encode.call_args.kwargs["normalize_embeddings"] is True
    assert emb.dim == 3
    assert emb.embed_documents([]) == []
