"""Tests for Prometheus request metrics instrumentation."""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI, Response

from prometheus_client import Counter, Histogram

from apps.mw.src.observability.metrics import (
    CALL_EXPORT_COST_TOTAL,
    CALL_EXPORT_DURATION_SECONDS,
    CALL_EXPORT_QA_CHECKED_TOTAL,
    CALL_EXPORT_REPORTS_TOTAL,
    CALL_EXPORT_RETRY_TOTAL,
    CALL_EXPORT_RUNS_TOTAL,
    CALL_EXPORT_TRANSCRIBE_FAILURES_TOTAL,
    CALL_TRANSCRIPTION_MINUTES_TOTAL,
    CALL_TRANSCRIPTS_TOTAL,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    RequestMetricsMiddleware,
)

BASE_URL = "http://testserver"


@pytest.mark.asyncio
async def test_request_metrics_increment_for_success_and_error() -> None:
    """Counter and histogram values increase for 2xx and 5xx responses."""

    app = FastAPI()
    app.add_middleware(RequestMetricsMiddleware)

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/fail")
    async def fail() -> Response:
        return Response(status_code=500)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        success_labels = ("GET", "200", "/ok")
        error_labels = ("GET", "500", "/fail")

        success_counter = HTTP_REQUESTS_TOTAL.labels(*success_labels)
        error_counter = HTTP_REQUESTS_TOTAL.labels(*error_labels)
        success_histogram = HTTP_REQUEST_DURATION_SECONDS.labels(*success_labels)
        error_histogram = HTTP_REQUEST_DURATION_SECONDS.labels(*error_labels)

        success_counter_before = success_counter._value.get()
        error_counter_before = error_counter._value.get()
        success_histogram_before = success_histogram._sum.get()
        error_histogram_before = error_histogram._sum.get()

        ok_response = await client.get("/ok")
        fail_response = await client.get("/fail")

    assert ok_response.status_code == 200
    assert fail_response.status_code == 500

    assert success_counter._value.get() == success_counter_before + 1
    assert error_counter._value.get() == error_counter_before + 1
    assert success_histogram._sum.get() > success_histogram_before
    assert error_histogram._sum.get() > error_histogram_before


def test_call_export_metrics_registered() -> None:
    """Dedicated call export metrics are registered with expected types."""

    assert isinstance(CALL_EXPORT_RUNS_TOTAL, Counter)
    assert CALL_EXPORT_RUNS_TOTAL._labelnames == ("status",)

    assert isinstance(CALL_EXPORT_DURATION_SECONDS, Histogram)
    assert CALL_EXPORT_DURATION_SECONDS._labelnames == ("stage", "status")

    assert isinstance(CALL_TRANSCRIPTS_TOTAL, Counter)
    assert CALL_TRANSCRIPTS_TOTAL._labelnames == ("status", "engine")

    assert isinstance(CALL_TRANSCRIPTION_MINUTES_TOTAL, Counter)
    assert CALL_TRANSCRIPTION_MINUTES_TOTAL._labelnames == ("engine",)

    assert isinstance(CALL_EXPORT_COST_TOTAL, Counter)
    assert CALL_EXPORT_COST_TOTAL._labelnames == ("currency",)

    assert isinstance(CALL_EXPORT_RETRY_TOTAL, Counter)
    assert CALL_EXPORT_RETRY_TOTAL._labelnames == ("stage",)

    assert isinstance(CALL_EXPORT_QA_CHECKED_TOTAL, Counter)
    assert CALL_EXPORT_QA_CHECKED_TOTAL._labelnames == ("result",)

    assert isinstance(CALL_EXPORT_TRANSCRIBE_FAILURES_TOTAL, Counter)
    assert CALL_EXPORT_TRANSCRIBE_FAILURES_TOTAL._labelnames == ("code",)

    assert isinstance(CALL_EXPORT_REPORTS_TOTAL, Counter)
    assert CALL_EXPORT_REPORTS_TOTAL._labelnames == ("format",)
