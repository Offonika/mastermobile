"""Unit tests for health payload helpers."""

from apps.mw.src.health import HEALTH_PAYLOAD, get_health_payload


def test_get_health_payload_returns_fresh_copy() -> None:
    """The health payload helper must not expose the module-level constant."""

    first_payload = get_health_payload()
    second_payload = get_health_payload()

    # A returned payload should be an independent copy.
    assert first_payload is not HEALTH_PAYLOAD
    assert first_payload is not second_payload

    # Mutating the returned payload must not leak back to the constant.
    first_payload["status"] = "broken"

    assert HEALTH_PAYLOAD["status"] == "ok"
    assert second_payload == {"status": "ok"}
    assert get_health_payload() == {"status": "ok"}
