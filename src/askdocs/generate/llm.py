"""LLM clients behind one interface: Claude (Anthropic SDK) or a local Ollama model.

``complete`` returns a Completion; ``stream`` yields text deltas and then, as
its last item, the Completion with usage. Provider errors are translated into
the LLMError hierarchy so the API maps them to HTTP status codes uniformly.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

import anthropic
import httpx

# USD per million tokens (input, output). Unknown models report cost as None.
PRICING = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

# Server-side refusal fallback: a declined request is re-run on Anthropic's
# recommended fallback model inside the same call.
_FALLBACK_HEADERS = {"anthropic-beta": "server-side-fallback-2026-07-01"}
_FALLBACK_BODY = {"fallbacks": "default"}


class LLMError(RuntimeError):
    pass


class LLMNotConfigured(LLMError):
    pass


class LLMRateLimited(LLMError):
    pass


class LLMTimeout(LLMError):
    pass


class LLMRefusal(LLMError):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0

    def __add__(self, other: "Usage") -> "Usage":
        cost = None if self.cost_usd is None or other.cost_usd is None else self.cost_usd + other.cost_usd
        return Usage(self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens, cost)


@dataclass
class Completion:
    text: str
    model: str
    usage: Usage = field(default_factory=Usage)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    if model not in PRICING:
        return None
    price_in, price_out = PRICING[model]
    return round((input_tokens * price_in + output_tokens * price_out) / 1_000_000, 6)


class LLMClient(Protocol):
    model: str

    def complete(self, system: str, messages: list[dict]) -> Completion: ...

    def stream(self, system: str, messages: list[dict]) -> Iterator[str | Completion]: ...


class AnthropicLLM:
    def __init__(
        self,
        model: str = "claude-opus-5-5",
        api_key: str | None = None,
        effort: str = "low",
        timeout_s: float = 30.0,
        max_tokens: int = 8000,
        client: anthropic.Anthropic | None = None,
    ):
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        # api_key=None lets the SDK resolve ANTHROPIC_API_KEY or an `ant auth login` profile.
        self._client = client or anthropic.Anthropic(api_key=api_key or None, timeout=timeout_s, max_retries=2)

    def _params(self, system: str, messages: list[dict]) -> dict:
        # Current Claude models reject sampling parameters, so no temperature here;
        # low effort keeps answers fast for the latency budget.
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": messages,
            "output_config": {"effort": self.effort},
            "extra_headers": _FALLBACK_HEADERS,
            "extra_body": _FALLBACK_BODY,
        }

    def _completion(self, message) -> Completion:
        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            raise LLMRefusal(getattr(details, "explanation", None) or "The model declined this request.")
        text = "".join(b.text for b in message.content if b.type == "text").strip()
        u = message.usage
        usage = Usage(u.input_tokens, u.output_tokens, cost_usd(self.model, u.input_tokens, u.output_tokens))
        return Completion(text, message.model, usage)

    def complete(self, system: str, messages: list[dict]) -> Completion:
        with _translate_anthropic_errors():
            return self._completion(self._client.messages.create(**self._params(system, messages)))

    def stream(self, system: str, messages: list[dict]) -> Iterator[str | Completion]:
        with _translate_anthropic_errors(), self._client.messages.stream(**self._params(system, messages)) as s:
            yield from s.text_stream
            yield self._completion(s.get_final_message())


class _translate_anthropic_errors:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None or isinstance(exc, LLMError | GeneratorExit):
            return False
        if isinstance(exc, anthropic.APITimeoutError):
            raise LLMTimeout("The LLM request timed out.") from exc
        if isinstance(exc, anthropic.RateLimitError):
            raise LLMRateLimited("The LLM provider rate-limited the request.") from exc
        if isinstance(exc, anthropic.AuthenticationError):
            raise LLMNotConfigured("Anthropic API key is missing or invalid.") from exc
        if isinstance(exc, anthropic.APIStatusError):
            raise LLMError(f"LLM provider error ({exc.status_code}): {exc.message}") from exc
        if isinstance(exc, anthropic.APIConnectionError):
            raise LLMError("Could not reach the LLM provider.") from exc
        if isinstance(exc, TypeError) and "authentication" in str(exc):  # SDK found no credentials
            raise LLMNotConfigured("No Anthropic credentials configured. Set LLM_API_KEY.") from exc
        return False


class OllamaLLM:
    """Local model through Ollama's /api/chat endpoint."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434", temperature: float = 0.1, timeout_s=60.0):
        self.model = model
        self.temperature = temperature
        self._http = httpx.Client(base_url=base_url, timeout=timeout_s)

    def _body(self, system: str, messages: list[dict], stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": stream,
            "options": {"temperature": self.temperature},
        }

    @staticmethod
    def _usage(data: dict) -> Usage:
        return Usage(data.get("prompt_eval_count", 0), data.get("eval_count", 0), 0.0)

    def complete(self, system: str, messages: list[dict]) -> Completion:
        with _translate_http_errors():
            r = self._http.post("/api/chat", json=self._body(system, messages, stream=False))
            r.raise_for_status()
            data = r.json()
        return Completion(data["message"]["content"].strip(), self.model, self._usage(data))

    def stream(self, system: str, messages: list[dict]) -> Iterator[str | Completion]:
        import json

        parts: list[str] = []
        body = self._body(system, messages, stream=True)
        with _translate_http_errors(), self._http.stream("POST", "/api/chat", json=body) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                delta = data.get("message", {}).get("content", "")
                if delta:
                    parts.append(delta)
                    yield delta
                if data.get("done"):
                    yield Completion("".join(parts).strip(), self.model, self._usage(data))
                    return


class _translate_http_errors:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None or isinstance(exc, LLMError | GeneratorExit):
            return False
        if isinstance(exc, httpx.TimeoutException):
            raise LLMTimeout("The local model timed out.") from exc
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
            raise LLMRateLimited("The local model is overloaded.") from exc
        if isinstance(exc, httpx.HTTPError):
            raise LLMError(f"Ollama request failed: {exc}") from exc
        return False


def make_llm(provider: str, model: str, **kwargs) -> LLMClient:
    if provider == "anthropic":
        return AnthropicLLM(
            model,
            api_key=kwargs.get("api_key"),
            effort=kwargs.get("effort", "low"),
            timeout_s=kwargs.get("timeout_s", 30),
        )
    if provider == "ollama":
        return OllamaLLM(
            model,
            base_url=kwargs.get("ollama_url", "http://localhost:11434"),
            temperature=kwargs.get("temperature", 0.1),
            timeout_s=kwargs.get("timeout_s", 60),
        )
    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Use 'anthropic' or 'ollama'.")
