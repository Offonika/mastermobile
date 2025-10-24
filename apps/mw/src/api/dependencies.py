"""Reusable FastAPI dependencies for headers, security and idempotency."""
from __future__ import annotations

import hashlib
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
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
_IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]
_PrincipalIdHeader = Annotated[str | None, Header(alias="X-Principal-Id", max_length=128)]
_PrincipalRolesHeader = Annotated[
    str | None, Header(alias="X-Principal-Roles", max_length=512)
]

@dataclass(slots=True)
class _IdempotencyRecord:
    """Stored fingerprint and response snapshot for an idempotent request."""

    digest: str
    response_status: int | None = None
    response_payload: object | None = None
    response_headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class IdempotencyContext:
    """Context returned by :func:`enforce_idempotency_key` for route handlers."""

    key: str
    cache_key: tuple[str, str, str]
    record: _IdempotencyRecord

    @property
    def is_replay(self) -> bool:
        """Indicate whether the incoming request matches a cached response."""

        return self.record.response_payload is not None

    def get_replay_payload(self) -> object:
        """Return cached payload for replayed requests."""

        return self.record.response_payload

    def get_replay_headers(self) -> dict[str, str]:
        """Return cached headers associated with the original response."""

        return dict(self.record.response_headers)

    def store_response(
        self,
        *,
        status_code: int,
        payload: object,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Persist the response snapshot for future identical requests."""

        with _IDEMPOTENCY_LOCK:
            entry = _IDEMPOTENCY_CACHE.get(self.cache_key)
            if entry is None or entry.response_payload is not None:
                return

            entry.response_status = status_code
            entry.response_payload = payload
            entry.response_headers = dict(headers or {})


_IDEMPOTENCY_CACHE: dict[tuple[str, str, str], _IdempotencyRecord] = {}
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
    idempotency_key: _IdempotencyKeyHeader = None,
    request_id: str = Depends(provide_request_id),
) -> IdempotencyContext:
    """Validate and track idempotency keys for unsafe HTTP operations."""

    key = (idempotency_key or "").strip()
    if not key:
        raise ProblemDetailException(
            build_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
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
        record = _IDEMPOTENCY_CACHE.get(cache_key)
        if record is None:
            record = _IdempotencyRecord(digest=digest)
            _IDEMPOTENCY_CACHE[cache_key] = record
        elif record.digest != digest:
            raise ProblemDetailException(
                build_error(
                    status.HTTP_409_CONFLICT,
                    title="Idempotency conflict",
                    detail="Payload differs from the original request for this Idempotency-Key.",
                    request_id=request_id,
                )
            )

    request.state.idempotency_key = key
    request.state.idempotency_record = record
    return IdempotencyContext(key=key, cache_key=cache_key, record=record)


def reset_idempotency_cache() -> None:
    """Clear stored idempotency fingerprints (primarily for tests)."""

    with _IDEMPOTENCY_LOCK:
        _IDEMPOTENCY_CACHE.clear()


@dataclass(slots=True, frozen=True)
class Principal:
    """Authenticated principal extracted from request headers."""

    subject: str
    roles: frozenset[str]
    request_id: str


def _parse_roles(raw_roles: str | None) -> frozenset[str]:
    if not raw_roles:
        return frozenset()
    roles = {role.strip().lower() for role in raw_roles.split(",") if role.strip()}
    return frozenset(roles)


def get_current_principal(
    principal_id: _PrincipalIdHeader = None,
    roles_header: _PrincipalRolesHeader = None,
    request_id: str = Depends(provide_request_id),
) -> Principal:
    """Build a :class:`Principal` from trusted proxy headers."""

    subject = (principal_id or "").strip()
    if not subject:
        raise ProblemDetailException(
            build_error(
                status.HTTP_401_UNAUTHORIZED,
                title="Missing principal identifier",
                detail="Header X-Principal-Id is required for authenticated requests.",
                request_id=request_id,
            )
        )

    roles = _parse_roles(roles_header)
    return Principal(subject=subject, roles=roles, request_id=request_id)


AdminPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_admin(principal: AdminPrincipal) -> Principal:
    """Ensure the current principal carries the administrator role."""

    if "admin" not in principal.roles:
        raise ProblemDetailException(
            build_error(
                status.HTTP_403_FORBIDDEN,
                title="Admin privileges required",
                detail="This endpoint is restricted to administrator principals.",
                request_id=principal.request_id,
            )
        )

    return principal
