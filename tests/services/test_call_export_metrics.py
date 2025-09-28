from prometheus_client import REGISTRY

import pytest

from apps.mw.src.services.call_export_metrics import (
    CallExportRunTracker,
    record_call_export_dlq,
    record_call_export_retry,
)


def _metric_value(name: str, labels: dict[str, str]) -> float:
    value = REGISTRY.get_sample_value(name, labels)
    return 0.0 if value is None else value


def test_call_export_run_tracker_records_success() -> None:
    started_before = _metric_value("call_export_runs_total", {"status": "started"})
    success_before = _metric_value("call_export_runs_total", {"status": "success"})
    count_before = _metric_value(
        "call_export_duration_seconds_count",
        {"status": "success"},
    )

    with CallExportRunTracker():
        pass

    assert (
        _metric_value("call_export_runs_total", {"status": "started"})
        == started_before + 1.0
    )
    assert (
        _metric_value("call_export_runs_total", {"status": "success"})
        == success_before + 1.0
    )
    assert (
        _metric_value("call_export_duration_seconds_count", {"status": "success"})
        == count_before + 1.0
    )


def test_call_export_run_tracker_records_failure() -> None:
    error_before = _metric_value("call_export_runs_total", {"status": "error"})
    count_before = _metric_value(
        "call_export_duration_seconds_count",
        {"status": "error"},
    )

    with pytest.raises(RuntimeError):
        with CallExportRunTracker():
            raise RuntimeError("boom")

    assert (
        _metric_value("call_export_runs_total", {"status": "error"})
        == error_before + 1.0
    )
    assert (
        _metric_value("call_export_duration_seconds_count", {"status": "error"})
        == count_before + 1.0
    )


def test_call_export_retry_and_dlq_helpers_increment_counters() -> None:
    retry_before = _metric_value(
        "call_export_retry_total", {"stage": "download", "reason": "retry"}
    )
    record_call_export_retry("download")
    assert (
        _metric_value("call_export_retry_total", {"stage": "download", "reason": "retry"})
        == retry_before + 1.0
    )

    dlq_before = _metric_value(
        "call_export_dlq_total", {"stage": "transcribe", "reason": "unknown"}
    )
    record_call_export_dlq("transcribe")
    assert (
        _metric_value(
            "call_export_dlq_total",
            {"stage": "transcribe", "reason": "unknown"},
        )
        == dlq_before + 1.0
    )

    custom_before = _metric_value(
        "call_export_dlq_total", {"stage": "transcribe", "reason": "whisper_5xx"}
    )
    record_call_export_dlq("transcribe", reason="whisper_5xx")
    assert (
        _metric_value(
            "call_export_dlq_total",
            {"stage": "transcribe", "reason": "whisper_5xx"},
        )
        == custom_before + 1.0
    )
