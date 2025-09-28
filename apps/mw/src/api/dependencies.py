"""Reusable FastAPI dependencies for headers, security and idempotency."""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
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
_PrincipalIdHeader = Annotated[str | None, Header(alias="X-Principal-Id", max_length=128)]
_PrincipalRolesHeader = Annotated[
    str | None, Header(alias="X-Principal-Roles", max_length=512)
]

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


def require_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
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
