"""Domain-level helpers for health-check responses."""

from __future__ import annotations

from datetime import UTC, datetime

HEALTH_PAYLOAD: dict[str, str] = {"status": "ok"}
PING_STATUS = "pong"
PING_SERVICE_IDENTIFIER = "master-mobile-middleware"


def get_health_payload() -> dict[str, str]:
    """Return the canonical payload for the health endpoint."""
    return HEALTH_PAYLOAD


def get_ping_payload(*, service: str | None = PING_SERVICE_IDENTIFIER) -> dict[str, str]:
    """Return the canonical payload for the ping endpoint."""
    payload: dict[str, str] = {
        "status": PING_STATUS,
        "timestamp": _current_utc_timestamp(),
    }
    if service:
        payload["service"] = service
    return payload


def _current_utc_timestamp() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return (
        datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
