"""OpenTelemetry tracing, exported over OTLP/HTTP to Arize Phoenix or Langfuse.

Spans are started with an explicit parent instead of being attached to the
current context, because streamed requests resume on different threads.
With TRACING_ENABLED=false the OpenTelemetry API is a no-op.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

_configured = False


def setup_tracing(enabled: bool, endpoint: str, service_name: str = "askdocs") -> bool:
    """Install the OTLP exporter once. Headers (e.g. Langfuse auth) come from OTEL_EXPORTER_OTLP_HEADERS."""
    global _configured
    if not enabled or _configured:
        return _configured
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    _configured = True
    return True


def tracer() -> trace.Tracer:
    return trace.get_tracer("askdocs")


@contextmanager
def span(name: str, parent: Span | None = None, **attributes) -> Iterator[Span]:
    context = trace.set_span_in_context(parent) if parent is not None else None
    s = tracer().start_span(name, context=context, attributes=_clean(attributes))
    try:
        yield s
    except BaseException as exc:
        if not isinstance(exc, GeneratorExit):
            s.record_exception(exc)
            s.set_status(Status(StatusCode.ERROR, str(exc)))
        raise
    finally:
        s.end()


def trace_id_hex(s: Span) -> str | None:
    ctx = s.get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else None


def _clean(attributes: dict) -> dict:
    return {k: v for k, v in attributes.items() if v is not None}
