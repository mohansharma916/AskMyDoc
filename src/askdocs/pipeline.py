"""Online query pipeline: retrieve -> rerank -> abstain check -> generate -> verify citations.

``ask`` returns a complete AskResult; ``ask_stream`` yields the same work as
events (meta, token, retry, done) for server-sent events. Every request is
logged to the traces table.
"""

import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass, field

from .generate.citations import check_citations, cited_numbers, is_not_found
from .generate.llm import Completion, LLMClient, Usage
from .generate.prompt import NOT_FOUND, PromptTemplate, build_retry_message, build_user_message
from .rerank.cross_encoder import Reranker
from .retrieve.hybrid import HybridRetriever, RetrievalMode, StageTimeout
from .retrieve.types import Candidate
from .store.db import Database
from .store.models import Trace

NOT_FOUND_MESSAGE = "I couldn't find the answer to that in the documents."
SNIPPET_CHARS = 300


@dataclass
class PipelineOptions:
    mode: RetrievalMode = "hybrid"
    rerank: bool = True
    validate_citations: bool = True


@dataclass
class Citation:
    n: int
    chunk_id: str
    doc_id: str
    file_name: str
    page: int | None
    section_path: list[str]
    snippet: str


@dataclass
class AskResult:
    query_id: str
    question: str
    answer: str
    abstained: bool
    abstain_reason: str | None
    citations: list[Citation]
    usage: Usage
    latency_ms: dict[str, int]
    model: str | None
    prompt_version: str
    contexts: list[Candidate] = field(default_factory=list, repr=False)  # chunks shown to the LLM
    ranked_chunk_ids: list[str] = field(default_factory=list, repr=False)  # full ranking, for eval metrics

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("contexts")
        data.pop("ranked_chunk_ids")
        return data


@dataclass
class Event:
    type: str  # meta | token | retry | done
    data: dict


def new_query_id() -> str:
    return "q_" + uuid.uuid4().hex[:20]


def _ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _snippet(text: str) -> str:
    return text if len(text) <= SNIPPET_CHARS else text[: SNIPPET_CHARS - 1].rsplit(" ", 1)[0] + "…"


def build_citations(answer: str, chunks: list[Candidate]) -> list[Citation]:
    used = sorted({n for n in cited_numbers(answer) if 1 <= n <= len(chunks)})
    return [
        Citation(
            n,
            chunks[n - 1].chunk_id,
            chunks[n - 1].doc_id,
            chunks[n - 1].file_name,
            chunks[n - 1].page,
            list(chunks[n - 1].section_path),
            _snippet(chunks[n - 1].text),
        )
        for n in used
    ]


class AskPipeline:
    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: Reranker,
        llm: LLMClient,
        prompt: PromptTemplate,
        db: Database | None = None,
        retrieve_k: int = 20,
        rerank_k: int = 5,
        abstain_threshold: float = 0.1,
        rerank_timeout_s: float = 20.0,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.llm = llm
        self.prompt = prompt
        self.db = db
        self.retrieve_k = retrieve_k
        self.rerank_k = rerank_k
        self.abstain_threshold = abstain_threshold
        self.rerank_timeout_s = rerank_timeout_s
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rerank")

    # --- stages ---------------------------------------------------------------

    def retrieve(
        self, question: str, doc_ids: list[str] | None, options: PipelineOptions, latency: dict
    ) -> list[Candidate]:
        """All retrieved candidates, best first (reranked when enabled); callers keep the top k."""
        start = time.perf_counter()
        candidates = self.retriever.retrieve(question, self.retrieve_k, doc_ids, options.mode)
        latency["retrieve"] = _ms(start)
        if options.rerank and candidates:
            start = time.perf_counter()
            future = self._pool.submit(self.reranker.rerank, question, candidates)
            try:
                candidates = future.result(timeout=self.rerank_timeout_s)
            except FutureTimeout as exc:
                raise StageTimeout("rerank", self.rerank_timeout_s) from exc
            latency["rerank"] = _ms(start)
        return candidates

    def abstain_reason(self, chunks: list[Candidate], options: PipelineOptions) -> str | None:
        if not chunks:
            return "no_results"
        if options.rerank and chunks[0].scores.get("rerank", 1.0) < self.abstain_threshold:
            return "low_confidence"
        return None

    def _messages(self, question: str, chunks: list[Candidate]) -> list[dict]:
        return [{"role": "user", "content": build_user_message(question, chunks)}]

    def _finish(
        self,
        query_id: str,
        question: str,
        answer: str,
        chunks: list[Candidate],
        usage: Usage,
        latency: dict,
        started: float,
        abstain_reason: str | None,
        ranked: list[Candidate],
    ) -> AskResult:
        latency["total"] = _ms(started)
        abstained = abstain_reason is not None
        result = AskResult(
            query_id=query_id,
            question=question,
            answer=NOT_FOUND_MESSAGE if abstained else answer,
            abstained=abstained,
            abstain_reason=abstain_reason,
            citations=[] if abstained else build_citations(answer, chunks),
            usage=usage,
            latency_ms=latency,
            model=self.llm.model if usage.input_tokens else None,
            prompt_version=self.prompt.version,
            contexts=chunks,
            ranked_chunk_ids=[c.chunk_id for c in ranked],
        )
        self._record(result)
        return result

    def _record(self, result: AskResult) -> None:
        if self.db is None:
            return
        with self.db.session() as s:
            s.add(
                Trace(
                    query_id=result.query_id,
                    question=result.question,
                    answer=result.answer,
                    abstained=result.abstained,
                    abstain_reason=result.abstain_reason,
                    citations=[asdict(c) for c in result.citations],
                    context_chunk_ids=[c.chunk_id for c in result.contexts],
                    usage=asdict(result.usage),
                    latency_ms=result.latency_ms,
                    model=result.model,
                    prompt_version=result.prompt_version,
                )
            )

    def _judge(self, text: str, n_chunks: int, options: PipelineOptions) -> tuple[str | None, list[str]]:
        """Returns (abstain_reason, citation issues) for one generation attempt."""
        if is_not_found(text):
            return "not_in_documents", []
        if not options.validate_citations:
            return None, []
        check = check_citations(text, n_chunks)
        return None, ([] if check.ok else check.issues)

    # --- public API -------------------------------------------------------------

    def ask(
        self,
        question: str,
        top_k: int | None = None,
        doc_ids: list[str] | None = None,
        options: PipelineOptions | None = None,
    ) -> AskResult:
        options = options or PipelineOptions()
        started, latency, usage = time.perf_counter(), {}, Usage()
        query_id = new_query_id()
        ranked = self.retrieve(question, doc_ids, options, latency)
        chunks = ranked[: top_k or self.rerank_k]
        if reason := self.abstain_reason(chunks, options):
            return self._finish(query_id, question, "", chunks, usage, latency, started, reason, ranked)

        start = time.perf_counter()
        messages = self._messages(question, chunks)
        for attempt in range(2):
            completion = self.llm.complete(self.prompt.system, messages)
            usage += completion.usage
            reason, issues = self._judge(completion.text, len(chunks), options)
            if reason or not issues:
                break
            if attempt == 0:  # one retry with the violations spelled out
                messages += [
                    {"role": "assistant", "content": completion.text},
                    {"role": "user", "content": build_retry_message(issues, len(chunks))},
                ]
            else:
                reason = "citation_check_failed"
        latency["generate"] = _ms(start)
        return self._finish(query_id, question, completion.text, chunks, usage, latency, started, reason, ranked)

    def ask_stream(
        self,
        question: str,
        top_k: int | None = None,
        doc_ids: list[str] | None = None,
        options: PipelineOptions | None = None,
    ) -> Iterator[Event]:
        options = options or PipelineOptions()
        started, latency, usage = time.perf_counter(), {}, Usage()
        query_id = new_query_id()
        yield Event("meta", {"query_id": query_id})

        ranked = self.retrieve(question, doc_ids, options, latency)
        chunks = ranked[: top_k or self.rerank_k]
        if reason := self.abstain_reason(chunks, options):
            result = self._finish(query_id, question, "", chunks, usage, latency, started, reason, ranked)
            yield Event("done", result.to_dict())
            return

        start = time.perf_counter()
        messages = self._messages(question, chunks)
        for attempt in range(2):
            completion: Completion | None = None
            held = ""  # hold back text while it could still be the NOT_FOUND reply
            for item in self.llm.stream(self.prompt.system, messages):
                if isinstance(item, Completion):
                    completion = item
                    continue
                if held is not None:
                    held += item
                    if NOT_FOUND.startswith(held.strip().strip("*`")[: len(NOT_FOUND)]):
                        continue
                    item, held = held, None
                yield Event("token", {"text": item})
            assert completion is not None
            if held and not is_not_found(held):  # short answer that only looked like NOT_FOUND
                yield Event("token", {"text": held})
            usage += completion.usage
            reason, issues = self._judge(completion.text, len(chunks), options)
            if reason or not issues:
                break
            if attempt == 0:
                yield Event("retry", {"reason": "citation_check_failed", "issues": issues})
                messages += [
                    {"role": "assistant", "content": completion.text},
                    {"role": "user", "content": build_retry_message(issues, len(chunks))},
                ]
            else:
                reason = "citation_check_failed"
        latency["generate"] = _ms(start)
        result = self._finish(query_id, question, completion.text, chunks, usage, latency, started, reason, ranked)
        yield Event("done", result.to_dict())
