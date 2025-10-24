"""Logging configuration and request correlation helpers."""
from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from typing import Any

from fastapi import FastAPI
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from apps.mw.src.api.dependencies import provide_request_id
from apps.mw.src.config import Settings, get_settings

_correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_SENSITIVE_EXACT = {"from", "to"}
_SENSITIVE_CALL_RECORD_KEYS = {
    "from_number",
    "to_number",
    "fromnumber",
    "tonumber",
    "call_from",
    "call_to",
    "caller_number",
    "callee_number",
    "source_number",
    "destination_number",
}
_SENSITIVE_SUBSTRINGS = (
    "phone",
    "email",
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
)
_MASKED_VALUE = "[REDACTED]"


def get_correlation_id() -> str | None:
    """Return the current correlation identifier from the context."""

    return _correlation_id_var.get()


@contextmanager
def correlation_context(correlation_id: str) -> Iterator[None]:
    """Temporarily bind the provided correlation id to the logging context."""

    token = _correlation_id_var.set(correlation_id)
    try:
        yield
    finally:
        _correlation_id_var.reset(token)


def _is_sensitive_key(key: str | None) -> bool:
    if key is None:
        return False
    normalized = key.lower()
    if normalized in _SENSITIVE_EXACT or normalized in _SENSITIVE_CALL_RECORD_KEYS:
        return True
    return any(part in normalized for part in _SENSITIVE_SUBSTRINGS)


def _mask_value(key: str | None, value: Any) -> Any:
    if isinstance(value, dict):
        return {inner_key: _mask_value(inner_key, inner_value) for inner_key, inner_value in value.items()}
    if isinstance(value, list):
        return [_mask_value(key, item) for item in value]
    if isinstance(value, tuple):
        return tuple(_mask_value(key, item) for item in value)
    if _is_sensitive_key(key):
        return _MASKED_VALUE
    return value


def _mask_extra(extra: dict[str, Any]) -> dict[str, Any]:
    return {key: _mask_value(key, value) for key, value in extra.items()}


def _build_patcher(settings: Settings) -> Callable[[Any], None]:
    def _patch(record: Any) -> None:
        correlation_id = _correlation_id_var.get()
        record.setdefault("extra", {})
        record["extra"]["correlation_id"] = correlation_id

        if settings.pii_masking_enabled:
            record["extra"] = _mask_extra(record["extra"])

    return _patch


def configure_logging(*, sink: Any | None = None) -> None:
    """Configure loguru to emit JSON logs with optional PII masking."""

    settings = get_settings()
    handler_sink = sink if sink is not None else sys.stdout

    logger.remove()
    logger.configure(
        handlers=[
            {
                "sink": handler_sink,
                "level": settings.log_level.upper(),
                "serialize": True,
                "backtrace": False,
                "diagnose": False,
            }
        ],
        extra={"correlation_id": None},
        patcher=_build_patcher(settings),
    )


def create_logging_lifespan(
    *, sink: Any | None = None
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Return a FastAPI lifespan context manager that initialises logging."""

    @asynccontextmanager
    async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(sink=sink)
        yield

    return _lifespan


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a correlation id to each request and logging context."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        provisional_response = Response()
        request_id = provide_request_id(provisional_response, request.headers.get("X-Request-Id"))
        request.state.request_id = request_id
        token: Token[str | None] = _correlation_id_var.set(request_id)

        try:
            response = await call_next(request)
        except Exception:
            raise
        else:
            provide_request_id(response, request_id)
            return response
        finally:
            _correlation_id_var.reset(token)
