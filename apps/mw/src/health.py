"""Domain-level helpers for health-check responses."""

HEALTH_PAYLOAD: dict[str, str] = {"status": "ok"}


def get_health_payload() -> dict[str, str]:
    """Return the canonical payload for the health endpoint."""
    return HEALTH_PAYLOAD
