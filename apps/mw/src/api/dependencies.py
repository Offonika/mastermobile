"""Common FastAPI dependencies for request context management."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from fastapi import Header, HTTPException, Response, status

_IDEMPOTENCY_CACHE: dict[tuple[str, str], str] = {}


def inject_request_id(
    response: Response,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> str:
    """Ensure that every response includes a request identifier header."""

    request_id = x_request_id or str(uuid4())
    response.headers["X-Request-Id"] = request_id
    return request_id


def _fingerprint_payload(payload: Any) -> str:
    """Generate a deterministic hash for the supplied payload."""

    if payload is None:
        return "__none__"

    if hasattr(payload, "model_dump"):
        serialised = payload.model_dump(mode="json", exclude_none=True)
    else:
        serialised = payload

    try:
        encoded = json.dumps(serialised, sort_keys=True, default=str).encode("utf-8")
    except TypeError:
        encoded = repr(serialised).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def validate_idempotency(
    *,
    key: str,
    payload: Any,
    scope: str,
    request_id: str | None = None,
) -> None:
    """Enforce that the same idempotency key is not reused with conflicting payloads."""

    fingerprint = _fingerprint_payload(payload)
    cache_key = (key, scope)
    stored = _IDEMPOTENCY_CACHE.get(cache_key)

    if stored is None:
        _IDEMPOTENCY_CACHE[cache_key] = fingerprint
        return

    if stored != fingerprint:
        detail = "Payload differs from the original request for the provided idempotency key."
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "about:blank",
                "title": "Conflict",
                "status": status.HTTP_409_CONFLICT,
                "detail": detail,
                "request_id": request_id,
            },
        )


def require_idempotency_key(
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> str:
    """Retrieve the mandatory idempotency key header."""

    return idempotency_key
