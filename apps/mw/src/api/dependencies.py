"""Reusable FastAPI dependencies for headers and idempotency handling."""
from __future__ import annotations

import hashlib
import threading
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, Header, Request, Response, status

from apps.mw.src.api.schemas import Error


class ProblemDetailException(Exception):
    """Exception carrying RFC7807 compliant payload."""

    def __init__(self, error: Error) -> None:
        super().__init__(error.title)
        self.error = error


_RequestIdHeader = Annotated[str | None, Header(alias="X-Request-Id", max_length=128)]
_IdempotencyKeyHeader = Annotated[str, Header(alias="Idempotency-Key", max_length=128)]

_IDEMPOTENCY_CACHE: dict[tuple[str, str, str], str] = {}
_IDEMPOTENCY_LOCK = threading.Lock()


def build_error(
    status_code: int,
    *,
    title: str,
    detail: str | None = None,
    request_id: str | None = None,
    type_: str = "about:blank",
    errors: list[dict[str, str]] | None = None,
) -> Error:
    """Construct a problem details object with optional metadata."""

    return Error(
        type=type_,
        title=title,
        status=status_code,
        detail=detail,
        errors=errors,
        request_id=request_id,
    )


def provide_request_id(response: Response, request_id: _RequestIdHeader = None) -> str:
    """Ensure every response has an `X-Request-Id` header."""

    value = (request_id or str(uuid4())).strip()
    if not value:
        value = str(uuid4())
    response.headers["X-Request-Id"] = value
    return value


async def enforce_idempotency_key(
    request: Request,
    response: Response,
    request_id: str = Depends(provide_request_id),
    idempotency_key: _IdempotencyKeyHeader = None,
) -> str:
    """Validate and track idempotency keys for unsafe HTTP operations."""

    key = (idempotency_key or "").strip()
    if not key:
        raise ProblemDetailException(
            build_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                title="Invalid Idempotency-Key header",
                detail="Idempotency-Key header must not be blank.",
                request_id=request_id,
            )
        )

    body = await request.body()
    digest = hashlib.sha256(body).hexdigest()
    cache_key = (request.method.upper(), request.url.path, key)

    response.headers["Idempotency-Key"] = key

    with _IDEMPOTENCY_LOCK:
        existing = _IDEMPOTENCY_CACHE.get(cache_key)
        if existing is None:
            _IDEMPOTENCY_CACHE[cache_key] = digest
        elif existing != digest:
            raise ProblemDetailException(
                build_error(
                    status.HTTP_409_CONFLICT,
                    title="Idempotency conflict",
                    detail="Payload differs from the original request for this Idempotency-Key.",
                    request_id=request_id,
                )
            )

    request.state.idempotency_key = key
    return key


def reset_idempotency_cache() -> None:
    """Clear stored idempotency fingerprints (primarily for tests)."""

    with _IDEMPOTENCY_LOCK:
        _IDEMPOTENCY_CACHE.clear()
