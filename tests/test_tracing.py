import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from askdocs import tracing

from .conftest import FakeLLM


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing, "tracer", lambda: provider.get_tracer("test"))
    return exporter


def by_name(exporter):
    return {s.name: s for s in exporter.get_finished_spans()}


def test_ask_emits_stage_spans_under_one_trace(make_services, spans):
    result = make_services().pipeline.ask("parental leave weeks")
    named = by_name(spans)
    assert {"ask", "retrieve", "rerank", "generate"} <= named.keys()
    root = named["ask"]
    assert all(s.context.trace_id == root.context.trace_id for s in named.values())
    assert named["generate"].parent.span_id == root.context.span_id
    assert root.attributes["abstained"] is False and root.attributes["input_tokens"] == 100
    assert named["rerank"].attributes["candidates"] >= 1
    assert result.trace_id == format(root.context.trace_id, "032x")


def test_stream_spans_and_trace_id_in_meta(make_services, spans):
    events = list(make_services().pipeline.ask_stream("parental leave weeks"))
    root = by_name(spans)["ask_stream"]
    assert events[0].data["trace_id"] == format(root.context.trace_id, "032x")
    assert by_name(spans)["generate"].attributes["streamed"] is True


def test_errors_are_recorded_on_spans(make_services, spans):
    llm = FakeLLM()
    llm.complete = lambda *a: 1 / 0
    with pytest.raises(ZeroDivisionError):
        make_services(llm=llm).pipeline.ask("parental leave weeks")
    assert not by_name(spans)["generate"].status.is_ok
    assert by_name(spans)["ask"].events[0].name == "exception"


def test_trace_id_is_none_without_tracing(make_services):
    assert make_services().pipeline.ask("parental leave weeks").trace_id is None


def test_setup_tracing(monkeypatch):
    installed = []
    monkeypatch.setattr(tracing, "_configured", False)
    monkeypatch.setattr(tracing.trace, "set_tracer_provider", installed.append)
    assert tracing.setup_tracing(False, "http://x") is False and installed == []
    assert tracing.setup_tracing(True, "http://localhost:6006/v1/traces") is True
    assert tracing.setup_tracing(True, "http://other") is True and len(installed) == 1
