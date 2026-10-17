"""Phase 3: golden dataset management and Ragas evaluation runs."""

import asyncio
import csv
import io
import json
import math
import threading
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, LLMContextRecall, ResponseRelevancy
from ragas.run_config import RunConfig

from .config import DATA_DIR, get_settings
from .embeddings import get_embeddings

GOLDEN_MIN, GOLDEN_MAX = 50, 200
HISTORY_FILE = DATA_DIR / "eval_history.json"


# --- Ragas judge model -------------------------------------------------------


class _JudgeChatAnthropic(ChatAnthropic):
    """Ragas sets `temperature` on the wrapped model; current Claude models reject
    sampling parameters, so strip them from the outgoing request."""

    def _get_request_payload(self, *args, **kwargs) -> dict:
        payload = super()._get_request_payload(*args, **kwargs)
        for key in ("temperature", "top_p", "top_k"):
            payload.pop(key, None)
        return payload


@lru_cache
def _judge_llm() -> LangchainLLMWrapper:
    s = get_settings()
    # Without an explicit key, ChatAnthropic falls back to the ANTHROPIC_API_KEY env var.
    auth = {"api_key": s.anthropic_api_key} if s.anthropic_api_key else {}
    return LangchainLLMWrapper(_JudgeChatAnthropic(model=s.llm_model, max_tokens=8000, **auth))


@lru_cache
def _judge_embeddings() -> LangchainEmbeddingsWrapper:
    return LangchainEmbeddingsWrapper(get_embeddings())


def _clean(value) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), 4)


def score_faithfulness(question: str, answer: str, contexts: list[str]) -> float | None:
    """Single-sample faithfulness, used live by Phase 3 queries."""
    metric = Faithfulness(llm=_judge_llm())
    sample = SingleTurnSample(user_input=question, response=answer, retrieved_contexts=contexts)
    return _clean(asyncio.run(metric.single_turn_ascore(sample)))


# --- Golden dataset ------------------------------------------------------------


def parse_golden(filename: str, data: bytes) -> list[dict]:
    """Accept JSON (list of objects) or CSV with question + ground_truth/answer columns."""
    text = data.decode("utf-8-sig")
    if filename.lower().endswith(".csv"):
        rows = list(csv.DictReader(io.StringIO(text)))
    else:
        rows = json.loads(text)
        if isinstance(rows, dict):
            rows = rows.get("items") or rows.get("data") or []
    if not isinstance(rows, list):
        raise ValueError("Golden dataset must be a list of question/answer objects.")

    items = []
    for i, row in enumerate(rows, start=1):
        question = (row.get("question") or row.get("user_input") or "").strip()
        truth = (row.get("ground_truth") or row.get("answer") or row.get("reference") or "").strip()
        if not question or not truth:
            raise ValueError(f"Row {i} needs both a question and a ground_truth/answer.")
        items.append({"id": i, "question": question, "ground_truth": truth})
    if not items:
        raise ValueError("Golden dataset is empty.")
    return items


def save_golden(items: list[dict]) -> None:
    path = get_settings().golden_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2), encoding="utf-8")


def load_golden() -> list[dict]:
    path = get_settings().golden_file
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def golden_warning(count: int) -> str | None:
    if GOLDEN_MIN <= count <= GOLDEN_MAX:
        return None
    return f"{count} pairs loaded; a reliable golden set has {GOLDEN_MIN}-{GOLDEN_MAX} verified pairs."


# --- Evaluation jobs -----------------------------------------------------------

_jobs: dict[str, dict] = {}
_history_lock = threading.Lock()


def load_history() -> list[dict]:
    return json.loads(HISTORY_FILE.read_text(encoding="utf-8")) if HISTORY_FILE.exists() else []


def _append_history(run: dict) -> None:
    with _history_lock:
        history = load_history()
        history.append(run)
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history[-50:], indent=2), encoding="utf-8")


def create_job(pipeline_phase: int, limit: int | None) -> dict:
    job = {
        "id": uuid.uuid4().hex[:12],
        "status": "queued",
        "pipeline_phase": pipeline_phase,
        "progress": {"done": 0, "total": 0},
        "result": None,
        "error": None,
        "limit": limit,
    }
    _jobs[job["id"]] = job
    return job


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)


def run_job(job_id: str) -> None:
    from .graph import run_query

    job = _jobs[job_id]
    try:
        golden = load_golden()
        if not golden:
            raise ValueError("No golden dataset uploaded.")
        if job["limit"]:
            golden = golden[: job["limit"]]

        job["status"] = "answering"
        job["progress"]["total"] = len(golden)
        started = time.perf_counter()
        samples, answers = [], []
        for item in golden:
            out = run_query(item["question"], job["pipeline_phase"])
            contexts = [c["text"] for c in out["citations"]]
            samples.append(
                {
                    "user_input": item["question"],
                    "retrieved_contexts": contexts,
                    "response": out["answer"],
                    "reference": item["ground_truth"],
                }
            )
            answers.append(out)
            job["progress"]["done"] += 1

        job["status"] = "scoring"
        result = evaluate(
            dataset=EvaluationDataset.from_list(samples),
            metrics=[Faithfulness(), ResponseRelevancy(), LLMContextRecall()],
            llm=_judge_llm(),
            embeddings=_judge_embeddings(),
            run_config=RunConfig(max_workers=4, timeout=300),
            show_progress=False,
        )
        df = result.to_pandas()

        thresholds = get_settings().thresholds
        metrics = {}
        for name, threshold in thresholds.items():
            value = _clean(df[name].mean()) if name in df else None
            metrics[name] = {"value": value, "threshold": threshold, "passed": value is not None and value >= threshold}

        rows = []
        for i, item in enumerate(golden):
            rows.append(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "ground_truth": item["ground_truth"],
                    "answer": answers[i]["answer"],
                    "declined": answers[i]["declined"],
                    **{name: _clean(df.iloc[i].get(name)) for name in thresholds},
                }
            )

        build = {
            "id": job_id,
            "build_number": len(load_history()) + 1,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_s": round(time.perf_counter() - started, 1),
            "pipeline_phase": job["pipeline_phase"],
            "samples": len(golden),
            "passed": all(m["passed"] for m in metrics.values()),
            "metrics": metrics,
            "rows": rows,
        }
        _append_history({k: v for k, v in build.items() if k != "rows"})
        job["result"] = build
        job["status"] = "completed"
    except Exception as exc:  # surfaced to the UI as a failed build
        job["status"] = "failed"
        job["error"] = f"{type(exc).__name__}: {exc}"
