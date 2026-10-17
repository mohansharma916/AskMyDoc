"""Faithfulness and answer correctness with Ragas, using Claude as the judge.

Imported only by evaluation runs (needs the `eval` extra).
"""

import math

from langchain_anthropic import ChatAnthropic
from ragas import EvaluationDataset, evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import FactualCorrectness, Faithfulness
from ragas.run_config import RunConfig


class _JudgeChatAnthropic(ChatAnthropic):
    """Ragas sets `temperature` on its judge model; current Claude models reject
    sampling parameters, so strip them from the outgoing request."""

    def _get_request_payload(self, *args, **kwargs) -> dict:
        payload = super()._get_request_payload(*args, **kwargs)
        for key in ("temperature", "top_p", "top_k"):
            payload.pop(key, None)
        return payload


def judge_llm(model: str, api_key: str | None = None) -> LangchainLLMWrapper:
    auth = {"api_key": api_key} if api_key else {}  # else ChatAnthropic reads ANTHROPIC_API_KEY
    return LangchainLLMWrapper(_JudgeChatAnthropic(model=model, max_tokens=8000, **auth))


def score(samples: list[dict], model: str, api_key: str | None = None) -> list[dict[str, float | None]]:
    """samples: user_input, response, retrieved_contexts, reference. Returns per-sample scores."""
    if not samples:
        return []
    metrics = [Faithfulness(), FactualCorrectness()]
    result = evaluate(
        dataset=EvaluationDataset.from_list(samples),
        metrics=metrics,
        llm=judge_llm(model, api_key),
        run_config=RunConfig(max_workers=4, timeout=300),
        show_progress=False,
    )
    df = result.to_pandas()
    names = {"faithfulness": metrics[0].name, "answer_correctness": metrics[1].name}

    def clean(v):
        return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)

    return [{key: clean(row.get(col)) for key, col in names.items()} for _, row in df.iterrows()]
