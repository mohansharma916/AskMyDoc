import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from askdocs.generate.llm import (
    AnthropicLLM,
    Completion,
    LLMError,
    LLMNotConfigured,
    LLMRateLimited,
    LLMRefusal,
    LLMTimeout,
    OllamaLLM,
    Usage,
    cost_usd,
    make_llm,
)


def message(text="Answer [1].", stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(explanation="declined"),
        model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=1000, output_tokens=100),
    )


def test_cost_and_usage_addition():
    assert cost_usd("claude-opus-5-5", 1_000_000, 100_000) == 6.0
    assert cost_usd("unknown", 1, 1) is None
    assert Usage(1, 2, 0.5) + Usage(3, 4, 0.25) == Usage(4, 6, 0.75)
    assert (Usage(1, 1, None) + Usage(1, 1, 1.0)).cost_usd is None


def test_anthropic_complete_sends_effort_and_fallback_and_skips_thinking():
    client = MagicMock()
    client.messages.create.return_value = message()
    llm = AnthropicLLM(client=client, effort="low")
    out = llm.complete("sys", [{"role": "user", "content": "q"}])
    assert out == Completion("Answer [1].", "claude-opus-5-5", Usage(1000, 100, 0.006))
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["output_config"] == {"effort": "low"}
    assert kwargs["extra_body"] == {"fallbacks": "default"}
    assert "temperature" not in kwargs


def test_anthropic_refusal():
    client = MagicMock()
    client.messages.create.return_value = message(stop_reason="refusal")
    with pytest.raises(LLMRefusal, match="declined"):
        AnthropicLLM(client=client).complete("s", [])


def test_anthropic_stream_yields_deltas_then_completion():
    stream = MagicMock()
    stream.text_stream = iter(["Ans", "wer [1]."])
    stream.get_final_message.return_value = message()
    client = MagicMock()
    client.messages.stream.return_value.__enter__.return_value = stream
    items = list(AnthropicLLM(client=client).stream("s", []))
    assert items[:2] == ["Ans", "wer [1]."]
    assert isinstance(items[-1], Completion) and items[-1].usage.output_tokens == 100


REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize(
    "error, expected",
    [
        (anthropic.APITimeoutError(REQ), LLMTimeout),
        (anthropic.RateLimitError("rl", response=httpx.Response(429, request=REQ), body=None), LLMRateLimited),
        (anthropic.AuthenticationError("auth", response=httpx.Response(401, request=REQ), body=None), LLMNotConfigured),
        (anthropic.InternalServerError("boom", response=httpx.Response(500, request=REQ), body=None), LLMError),
        (anthropic.APIConnectionError(request=REQ), LLMError),
        (TypeError("Could not resolve authentication method"), LLMNotConfigured),
    ],
)
def test_anthropic_error_translation(error, expected):
    client = MagicMock()
    client.messages.create.side_effect = error
    with pytest.raises(expected):
        AnthropicLLM(client=client).complete("s", [])


def test_unrelated_errors_propagate():
    client = MagicMock()
    client.messages.create.side_effect = KeyError("x")
    with pytest.raises(KeyError):
        AnthropicLLM(client=client).complete("s", [])


def ollama(handler) -> OllamaLLM:
    llm = OllamaLLM("llama3.1", temperature=0.1)
    llm._http = httpx.Client(base_url="http://ollama", transport=httpx.MockTransport(handler))
    return llm


def test_ollama_complete_and_stream():
    def handler(request):
        body = json.loads(request.content)
        assert body["messages"][0] == {"role": "system", "content": "sys"}
        assert body["options"] == {"temperature": 0.1}
        if not body["stream"]:
            data = {"message": {"content": " Hi [1]. "}, "prompt_eval_count": 5, "eval_count": 2}
            return httpx.Response(200, json=data)
        lines = [
            {"message": {"content": "Hi"}, "done": False},
            {"message": {"content": " [1]."}, "done": False},
            {"message": {"content": ""}, "done": True, "prompt_eval_count": 5, "eval_count": 2},
        ]
        return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines))

    llm = ollama(handler)
    assert llm.complete("sys", []) == Completion("Hi [1].", "llama3.1", Usage(5, 2, 0.0))
    items = list(llm.stream("sys", []))
    assert items[:2] == ["Hi", " [1]."] and items[2].text == "Hi [1]."


def test_ollama_errors():
    with pytest.raises(LLMRateLimited):
        ollama(lambda r: httpx.Response(429)).complete("s", [])
    with pytest.raises(LLMError):
        ollama(lambda r: httpx.Response(500)).complete("s", [])

    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMTimeout):
        ollama(slow).complete("s", [])


def test_make_llm():
    assert isinstance(make_llm("anthropic", "claude-opus-5-5", api_key="k"), AnthropicLLM)
    assert isinstance(make_llm("ollama", "llama3.1"), OllamaLLM)
    with pytest.raises(ValueError):
        make_llm("openai", "x")
