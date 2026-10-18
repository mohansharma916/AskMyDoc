from sqlalchemy import select

from askdocs.pipeline import NOT_FOUND_MESSAGE, PipelineOptions, build_citations
from askdocs.retrieve.types import Candidate
from askdocs.store.models import Trace

from .conftest import FakeLLM


def test_cited_answer_with_usage_latency_and_trace(make_services):
    services = make_services()
    result = services.pipeline.ask("How many weeks of parental leave do primary caregivers get?")
    assert not result.abstained
    assert result.answer.endswith("[1].")
    [cite] = result.citations
    assert (cite.n, cite.doc_id, cite.file_name, cite.section_path) == (1, "leave", "leave.md", ["Leave"])
    assert "20 weeks" in cite.snippet
    assert result.usage.input_tokens == 100 and result.model == "fake-llm"
    assert {"retrieve", "rerank", "generate", "total"} <= result.latency_ms.keys()
    assert result.prompt_version == "answer_v3"

    with services.db.session() as s:
        trace = s.scalars(select(Trace)).one()
    assert trace.query_id == result.query_id and trace.citations[0]["chunk_id"] == cite.chunk_id
    assert trace.context_chunk_ids == [c.chunk_id for c in result.contexts]
    assert result.ranked_chunk_ids[: len(result.contexts)] == trace.context_chunk_ids
    assert len(result.ranked_chunk_ids) == 3  # every retrieved chunk, not just the top k


def test_prompt_contains_numbered_chunks(make_services):
    llm = FakeLLM()
    make_services(llm=llm).pipeline.ask("parental leave weeks")
    content = llm.calls[0][0]["content"]
    assert content.startswith("Excerpts:\n\n[1] (leave.md, section: Leave)")
    assert content.endswith("Question: parental leave weeks")


def test_low_rerank_score_abstains_without_calling_llm(make_services):
    llm = FakeLLM()
    result = make_services(llm=llm, abstain_threshold=0.9).pipeline.ask("parental leave policy for pets")
    assert result.abstained and result.abstain_reason == "low_confidence"
    assert result.answer == NOT_FOUND_MESSAGE and result.citations == []
    assert llm.calls == [] and result.model is None


def test_no_results_abstains(make_services):
    result = make_services(ingest=False).pipeline.ask("anything at all")
    assert result.abstain_reason == "no_results"


def test_model_not_found_reply_abstains(make_services):
    result = make_services(llm=FakeLLM("NOT_FOUND")).pipeline.ask("parental leave weeks")
    assert result.abstained and result.abstain_reason == "not_in_documents"


def test_partial_answer_keeps_supported_part(make_services):
    reply = "Primary caregivers receive 20 weeks of parental leave [1]. The documents do not say how leave is paid."
    llm = FakeLLM(reply)
    result = make_services(llm=llm).pipeline.ask("How many weeks of parental leave, and how is it paid?")
    assert not result.abstained and result.answer == reply
    assert [c.n for c in result.citations] == [1] and len(llm.calls) == 1  # no retry


def test_reply_of_only_gaps_abstains(make_services):
    result = make_services(llm=FakeLLM("The documents do not say how leave is paid.")).pipeline.ask("leave pay")
    assert result.abstained and result.abstain_reason == "not_in_documents"


def test_conflicting_sources_both_reach_the_model_and_are_cited(make_services):
    reply = (
        "The documents disagree: directory.md names Maria Okafor as CEO [1], while update.md names Daniel Reyes [2]."
    )
    llm = FakeLLM(reply)
    services = make_services(llm=llm, ingest=False)
    services.indexer.ingest_files(
        [
            ("directory.md", b"# Directory\n\nThe CEO of Northwind is Maria Okafor.", "directory.md"),
            ("update.md", b"# Update\n\nThe CEO of Northwind is Daniel Reyes.", "update.md"),
        ]
    )
    result = services.pipeline.ask("Who is the CEO of Northwind?")
    prompt = llm.calls[0][0]["content"]
    assert "Maria Okafor" in prompt and "Daniel Reyes" in prompt
    assert not result.abstained and result.answer == reply and len(llm.calls) == 1
    assert {c.file_name for c in result.citations} == {"directory.md", "update.md"}


def test_invalid_citations_trigger_one_retry(make_services):
    llm = FakeLLM("Caregivers get twenty weeks of leave.", "Caregivers get twenty weeks of leave [1].")
    result = make_services(llm=llm).pipeline.ask("parental leave weeks")
    assert not result.abstained and len(llm.calls) == 2
    retry = llm.calls[1]
    assert [m["role"] for m in retry] == ["user", "assistant", "user"]
    assert "Sentence without a citation" in retry[2]["content"]
    assert result.usage.input_tokens == 200  # usage summed across attempts


def test_second_invalid_answer_abstains(make_services):
    llm = FakeLLM("No citation here at all.", "Still citing a missing excerpt [9].")
    result = make_services(llm=llm).pipeline.ask("parental leave weeks")
    assert result.abstained and result.abstain_reason == "citation_check_failed"
    assert len(llm.calls) == 2


def test_options_disable_rerank_and_validation(make_services):
    llm = FakeLLM("Twenty weeks of leave without citations.")
    options = PipelineOptions(mode="bm25", rerank=False, validate_citations=False)
    result = make_services(llm=llm, abstain_threshold=0.99).pipeline.ask("parental leave", options=options)
    assert not result.abstained and "rerank" not in result.latency_ms
    assert len(llm.calls) == 1


def test_top_k_and_doc_filter(make_services):
    services = make_services()
    result = services.pipeline.ask("reported laptops", top_k=1, doc_ids=["it"])
    assert [c.doc_id for c in result.contexts] == ["it"]


def test_stream_events_and_not_found_hold_back(make_services):
    events = list(make_services().pipeline.ask_stream("parental leave weeks"))
    assert events[0].type == "meta" and events[-1].type == "done"
    text = "".join(e.data["text"] for e in events if e.type == "token")
    assert text == "Primary caregivers receive 20 weeks of parental leave [1]."
    assert events[-1].data["citations"][0]["n"] == 1

    events = list(make_services(llm=FakeLLM("NOT_FOUND")).pipeline.ask_stream("parental leave weeks"))
    assert not [e for e in events if e.type == "token"]  # NOT_FOUND is never shown to the user
    assert events[-1].data["abstained"] is True


def test_stream_retry_and_early_abstain(make_services):
    llm = FakeLLM("No citation in this answer.", "Twenty weeks of leave [1].")
    events = list(make_services(llm=llm).pipeline.ask_stream("parental leave weeks"))
    assert [e.type for e in events if e.type in ("retry", "done")] == ["retry", "done"]
    assert events[-1].data["abstained"] is False

    events = list(make_services(abstain_threshold=0.99).pipeline.ask_stream("parental leave pets"))
    assert [e.type for e in events] == ["meta", "done"]

    # A short reply that only looks like NOT_FOUND is still shown, then fails the citation check.
    events = list(make_services(llm=FakeLLM("NOT")).pipeline.ask_stream("parental leave weeks"))
    assert "".join(e.data["text"] for e in events if e.type == "token") == "NOTNOT"
    assert events[-1].data["abstain_reason"] == "citation_check_failed"


def test_build_citations_dedupes_and_ignores_out_of_range():
    chunks = [Candidate("c1", "d", "x" * 400, file_name="f"), Candidate("c2", "d", "short")]
    cites = build_citations("A [2][1]. B [1]. C [7].", chunks)
    assert [c.n for c in cites] == [1, 2]
    assert cites[0].snippet.endswith("…") and len(cites[0].snippet) <= 300
