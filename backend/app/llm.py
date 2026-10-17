"""Claude calls used by the query pipelines (official Anthropic SDK)."""

from functools import lru_cache

import anthropic
from pydantic import BaseModel, Field

from .config import get_settings

# Server-side refusal fallback: if a safety classifier declines, the API re-runs
# the request on Anthropic's recommended fallback model within the same call.
_FALLBACK_HEADERS = {"anthropic-beta": "server-side-fallback-2026-07-01"}
_FALLBACK_BODY = {"fallbacks": "default"}


class LLMRefusal(RuntimeError):
    pass


class SupportCheck(BaseModel):
    supported: bool = Field(description="True if the passages contain enough information to answer.")
    reason: str = Field(description="One sentence explaining the decision.")


@lru_cache
def get_client() -> anthropic.Anthropic:
    # Empty key -> None lets the SDK resolve ANTHROPIC_API_KEY / `ant auth login` profiles.
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key or None)


def _check_refusal(response) -> None:
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        raise LLMRefusal(getattr(details, "explanation", None) or "The model declined this request.")


def _call(method, **kwargs):
    try:
        response = method(**kwargs)
    except TypeError as exc:  # raised by the SDK before sending when no credentials resolve
        if "authentication" in str(exc):
            raise RuntimeError("Anthropic credentials not configured. Set ANTHROPIC_API_KEY in backend/.env.") from exc
        raise
    _check_refusal(response)
    return response


def generate(system: str, user: str, effort: str | None = None) -> str:
    s = get_settings()
    response = _call(
        get_client().messages.create,
        model=s.llm_model,
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort or s.llm_effort},
        extra_headers=_FALLBACK_HEADERS,
        extra_body=_FALLBACK_BODY,
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def check_support(system: str, user: str) -> SupportCheck:
    response = _call(
        get_client().messages.parse,
        model=get_settings().llm_model,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=SupportCheck,
        output_config={"effort": "low"},
        extra_headers=_FALLBACK_HEADERS,
        extra_body=_FALLBACK_BODY,
    )
    return response.parsed_output
