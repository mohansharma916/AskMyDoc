"""LangGraph execution router: one graph, three paths selected by phase_target.

  Phase 1: vector_search -> generate_basic
  Phase 2: hybrid_search -> rerank -> guardrail -> generate_grounded
  Phase 3: Phase 2 path  -> live_evaluation (Ragas faithfulness on this answer)
"""

import operator
import re
import time
from functools import lru_cache
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from . import llm, vectorstore
from .config import get_settings
from .prompts import format_context, render
from .reranker import get_reranker

DECLINE_MESSAGE = (
    "I can't answer that from the uploaded documents. "
    "The retrieved passages don't contain enough information to support an answer."
)
INSUFFICIENT = "INSUFFICIENT_CONTEXT"


class RAGState(TypedDict, total=False):
    question: str
    phase: int
    chunks: list[dict]
    answer: str
    declined: bool
    decline_reason: str | None
    prompt_name: str
    prompt_version: str
    faithfulness: float | None
    trace: Annotated[list[dict], operator.add]


def _step(name: str, started: float, detail: str) -> list[dict]:
    return [{"step": name, "detail": detail, "ms": round((time.perf_counter() - started) * 1000)}]


# --- Nodes -----------------------------------------------------------------


def vector_search(state: RAGState) -> RAGState:
    t = time.perf_counter()
    k = get_settings().top_k
    chunks = vectorstore.vector_search(state["question"], k)
    return {"chunks": chunks, "trace": _step("Vector search", t, f"Top {k} by cosine similarity -> {len(chunks)} chunks")}


def hybrid_search(state: RAGState) -> RAGState:
    t = time.perf_counter()
    s = get_settings()
    chunks = vectorstore.hybrid_search(state["question"], s.hybrid_candidates, s.hybrid_alpha)
    return {
        "chunks": chunks,
        "trace": _step("Hybrid search", t, f"BM25 + vector (alpha={s.hybrid_alpha}) -> {len(chunks)} candidates"),
    }


def rerank(state: RAGState) -> RAGState:
    t = time.perf_counter()
    s = get_settings()
    reranker = get_reranker()
    ranked = reranker.rerank(state["question"], state["chunks"], s.rerank_top_n)
    return {"chunks": ranked, "trace": _step("Re-rank", t, f"{reranker.name} kept top {len(ranked)}")}


def guardrail(state: RAGState) -> RAGState:
    t = time.perf_counter()
    s = get_settings()
    relevant = [c for c in state["chunks"] if c["score"] >= s.rerank_min_score]
    if not relevant:
        return {
            "declined": True,
            "decline_reason": f"No passage scored above the re-rank threshold ({s.rerank_min_score}).",
            "trace": _step("Citation guardrail", t, "Declined: no relevant passages"),
        }

    system, user, version = render("phase2_guardrail", context=format_context(relevant), question=state["question"])
    check = llm.check_support(system, user)
    detail = f"{'Supported' if check.supported else 'Declined'} (guardrail prompt v{version}): {check.reason}"
    return {
        "chunks": relevant,
        "declined": not check.supported,
        "decline_reason": None if check.supported else check.reason,
        "trace": _step("Citation guardrail", t, detail),
    }


def generate_basic(state: RAGState) -> RAGState:
    t = time.perf_counter()
    if not state["chunks"]:
        return {
            "answer": "No documents have been uploaded yet, so there is nothing to search.",
            "declined": True,
            "trace": _step("LLM generation", t, "Skipped: empty index"),
        }
    system, user, version = render("phase1_answer", context=format_context(state["chunks"]), question=state["question"])
    answer = llm.generate(system, user)
    return {
        "answer": answer,
        "declined": False,
        "prompt_name": "phase1_answer",
        "prompt_version": version,
        "trace": _step("LLM generation", t, f"Base prompt v{version}"),
    }


def generate_grounded(state: RAGState) -> RAGState:
    t = time.perf_counter()
    system, user, version = render("phase2_answer", context=format_context(state["chunks"]), question=state["question"])
    answer = llm.generate(system, user)
    meta = {"prompt_name": "phase2_answer", "prompt_version": version}
    if INSUFFICIENT in answer:
        return {
            **meta,
            "declined": True,
            "decline_reason": "The model reported the passages were insufficient.",
            "trace": _step("LLM generation", t, f"Versioned prompt v{version}: declined"),
        }
    return {**meta, "answer": answer, "trace": _step("LLM generation", t, f"Versioned prompt v{version}")}


def live_evaluation(state: RAGState) -> RAGState:
    from .evaluation import score_faithfulness  # Ragas is heavy; import on first use

    t = time.perf_counter()
    score = score_faithfulness(state["question"], state["answer"], [c["text"] for c in state["chunks"]])
    shown = "n/a" if score is None else f"{score:.2f}"
    return {"faithfulness": score, "trace": _step("Ragas faithfulness", t, f"Score {shown}")}


# --- Routing ---------------------------------------------------------------


def route_by_phase(state: RAGState) -> str:
    return "vector_search" if state["phase"] == 1 else "hybrid_search"


def after_guardrail(state: RAGState) -> str:
    return END if state.get("declined") else "generate_grounded"


def after_generation(state: RAGState) -> str:
    if state.get("declined") or state["phase"] != 3:
        return END
    return "live_evaluation"


@lru_cache
def build_graph():
    g = StateGraph(RAGState)
    for node in (vector_search, hybrid_search, rerank, guardrail, generate_basic, generate_grounded, live_evaluation):
        g.add_node(node.__name__, node)

    g.add_conditional_edges(START, route_by_phase, ["vector_search", "hybrid_search"])
    g.add_edge("vector_search", "generate_basic")
    g.add_edge("generate_basic", END)
    g.add_edge("hybrid_search", "rerank")
    g.add_edge("rerank", "guardrail")
    g.add_conditional_edges("guardrail", after_guardrail, ["generate_grounded", END])
    g.add_conditional_edges("generate_grounded", after_generation, ["live_evaluation", END])
    g.add_edge("live_evaluation", END)
    return g.compile()


# --- Public API ------------------------------------------------------------

_CITATION = re.compile(r"\[(\d+)\]")


def run_query(question: str, phase: int) -> dict:
    state = build_graph().invoke({"question": question, "phase": phase, "trace": []})
    declined = bool(state.get("declined"))
    answer = (state.get("answer") or DECLINE_MESSAGE) if declined else state.get("answer", "")
    cited = {int(n) for n in _CITATION.findall(answer)}
    citations = [
        {**chunk, "index": i, "cited": i in cited} for i, chunk in enumerate(state.get("chunks", []), start=1)
    ]
    return {
        "question": question,
        "phase": phase,
        "answer": answer,
        "declined": declined,
        "decline_reason": state.get("decline_reason"),
        "citations": citations,
        "prompt_name": state.get("prompt_name"),
        "prompt_version": state.get("prompt_version"),
        "faithfulness": state.get("faithfulness"),
        "trace": state.get("trace", []),
    }
