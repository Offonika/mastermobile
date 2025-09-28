"""End-to-end verification that call export metrics are exposed."""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

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
    register_metrics,
)

_BASE_URL = "http://testserver"


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_call_export_metrics() -> None:
    """The `/metrics` endpoint publishes the call export series."""

    app = FastAPI()
    register_metrics(app)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=_BASE_URL) as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    payload = response.text

    metric_names = (
        CALL_EXPORT_RUNS_TOTAL._name,
        CALL_EXPORT_DURATION_SECONDS._name,
        CALL_TRANSCRIPTS_TOTAL._name,
        CALL_TRANSCRIPTION_MINUTES_TOTAL._name,
        CALL_EXPORT_COST_TOTAL._name,
        CALL_EXPORT_RETRY_TOTAL._name,
        CALL_EXPORT_QA_CHECKED_TOTAL._name,
        CALL_EXPORT_TRANSCRIBE_FAILURES_TOTAL._name,
        CALL_EXPORT_REPORTS_TOTAL._name,
    )

    for metric in metric_names:
        assert f"# HELP {metric}" in payload
