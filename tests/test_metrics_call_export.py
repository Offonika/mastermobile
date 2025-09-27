"""Tests for Prometheus metrics exposed by the call export workflow."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.mw.src.app import app
from apps.mw.src.db.models import CallExportStatus
from apps.mw.src.observability import reset_call_export_metrics
from jobs.call_export import run_call_export


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    """Ensure each test starts with clean metric series."""

    reset_call_export_metrics()


def test_metrics_endpoint_reports_call_export_samples() -> None:
    """Call export runner metrics should appear on the /metrics endpoint."""

    attempts = {"count": 0}

    def successful_after_retry() -> CallExportStatus:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary failure")
        return CallExportStatus.COMPLETED

    status = run_call_export(
        successful_after_retry,
        max_retries=1,
        retry_exceptions=(RuntimeError,),
    )
    assert status is CallExportStatus.COMPLETED

    def failing_task() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        run_call_export(failing_task, max_retries=0, retry_exceptions=(RuntimeError,))

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.text

    assert 'call_export_runs_total{status="completed"} 1.0' in body
    assert 'call_export_runs_total{status="error"} 1.0' in body
    assert 'call_export_retry_total 1.0' in body
    assert 'call_export_duration_seconds_count 2.0' in body

    # Ensure counters and histograms received positive observations via registry output
    assert body.count("call_export_runs_total") >= 2
