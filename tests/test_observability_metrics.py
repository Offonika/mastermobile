"""Tests for Prometheus request metrics instrumentation."""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI, Response

from apps.mw.src.observability.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
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
