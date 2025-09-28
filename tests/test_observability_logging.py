"""Tests for logging correlation id injection and PII masking."""
from __future__ import annotations

import asyncio
import io
import json

from loguru import logger
from starlette.requests import Request
from starlette.responses import Response

from apps.mw.src.config.settings import get_settings
from apps.mw.src.observability.logging import (
    RequestContextMiddleware,
    configure_logging,
)


def _parse_logs(buffer: io.StringIO) -> list[dict[str, object]]:
    buffer.seek(0)
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    return [json.loads(line)["record"] for line in lines]


def test_pii_masking_masks_sensitive_fields_when_enabled(monkeypatch) -> None:
    """PII masking replaces sensitive fields with a redacted marker."""

    monkeypatch.setenv("PII_MASKING_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "local")
    get_settings.cache_clear()

    buffer = io.StringIO()
    configure_logging(sink=buffer)

    logger.bind(
        event="call_export.download",
        stage="test",
        call_id="call-123",
        phone_number="+79001234567",
        email="agent@example.com",
    ).info("PII masking test")

    records = _parse_logs(buffer)
    assert records, "Expected at least one log entry"
    extra = records[-1]["extra"]
    assert extra["phone_number"] == "[REDACTED]"
    assert extra["email"] == "[REDACTED]"


def test_pii_masking_masks_call_record_numbers(monkeypatch) -> None:
    """PII masking redacts call record number fields and nested structures."""

    monkeypatch.setenv("PII_MASKING_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "local")
    get_settings.cache_clear()

    buffer = io.StringIO()
    configure_logging(sink=buffer)

    logger.bind(
        event="call_export.download",
        from_number="+79005554433",
        to_number="+79000001122",
        metadata={
            "call": {"from_number": "+79001231212"},
            "recipients": [{"to_number": "+79009998877"}],
        },
    ).info("Call record masking test")

    records = _parse_logs(buffer)
    assert records, "Expected at least one log entry"
    extra = records[-1]["extra"]
    assert extra["from_number"] == "[REDACTED]"
    assert extra["to_number"] == "[REDACTED]"
    assert extra["metadata"]["call"]["from_number"] == "[REDACTED]"
    assert extra["metadata"]["recipients"][0]["to_number"] == "[REDACTED]"


async def test_request_context_injects_request_id_into_logs(monkeypatch) -> None:
    """Request middleware injects correlation id for main and background tasks."""

    monkeypatch.delenv("PII_MASKING_ENABLED", raising=False)
    get_settings.cache_clear()

    buffer = io.StringIO()
    configure_logging(sink=buffer)

    middleware = RequestContextMiddleware(lambda scope, receive, send: None)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/log",
        "headers": [(b"x-request-id", b"req-789")],
        "query_string": b"",
        "client": ("test", 0),
        "server": ("test", 80),
        "scheme": "http",
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)

    async def call_next(_: Request) -> Response:
        logger.bind(event="test", stage="main", call_id="call-456").info("main request log")

        async def background() -> None:
            logger.bind(event="test", stage="background", call_id="call-456").info("background log")

        await asyncio.create_task(background())
        return Response(status_code=200)

    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200
    assert response.headers.get("X-Request-Id") == "req-789"

    records = _parse_logs(buffer)
    assert len(records) >= 2
    assert {entry["extra"]["correlation_id"] for entry in records} == {"req-789"}


def test_pii_masking_defaults_to_enabled_outside_local(monkeypatch) -> None:
    """PII masking automatically enables itself for non-local environments."""

    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("PII_MASKING_ENABLED", raising=False)
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.pii_masking_enabled is True

    get_settings.cache_clear()
