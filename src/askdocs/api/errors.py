"""Uniform error responses: {"error": {"code", "message", "trace_id"}}."""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..generate.llm import LLMError, LLMNotConfigured, LLMRateLimited, LLMRefusal, LLMTimeout
from ..retrieve.hybrid import StageTimeout

log = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def error_body(code: str, message: str, trace_id: str | None = None) -> dict:
    return {"error": {"code": code, "message": message, "trace_id": trace_id or "t_" + uuid.uuid4().hex[:16]}}


def classify(exc: Exception) -> tuple[int, str, str]:
    """Map any exception to (status, code, message) — shared by JSON and SSE responses."""
    if isinstance(exc, APIError):
        return exc.status, exc.code, exc.message
    if isinstance(exc, LLMRateLimited):
        return 429, "rate_limited", str(exc)
    if isinstance(exc, LLMTimeout | StageTimeout):
        return 504, "timeout", str(exc)
    if isinstance(exc, LLMRefusal):
        return 422, "refused", str(exc)
    if isinstance(exc, LLMNotConfigured | LLMError):
        return 500, "internal_error", str(exc)
    return 500, "internal_error", "Unexpected server error."


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ())[1:])
        message = f"{where}: {first.get('msg', 'invalid request')}" if where else first.get("msg", "invalid request")
        return JSONResponse(error_body("invalid_request", message), status_code=400)

    @app.exception_handler(Exception)
    async def _any(_: Request, exc: Exception):
        status, code, message = classify(exc)
        body = error_body(code, message)
        if status >= 500:
            log.exception("request failed (trace_id=%s)", body["error"]["trace_id"], exc_info=exc)
        return JSONResponse(body, status_code=status)
