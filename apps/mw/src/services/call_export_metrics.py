"""Utility helpers for instrumenting the call export workflow metrics."""
from __future__ import annotations

from time import perf_counter

from apps.mw.src.observability import (
    CALL_EXPORT_DLQ_TOTAL,
    CALL_EXPORT_DURATION_SECONDS,
    CALL_EXPORT_RETRY_TOTAL,
    CALL_EXPORT_RUNS_TOTAL,
)


class CallExportRunTracker:
    """Track metrics for a single call export run lifecycle."""

    def __init__(self) -> None:
        self._started_at = perf_counter()
        self._closed = False
        CALL_EXPORT_RUNS_TOTAL.labels(status="started").inc()

    def mark_completed(self, *, status: str = "success") -> None:
        """Record a successful completion status for the run."""

        self._close(status=status)

    def mark_failed(self, *, status: str = "error") -> None:
        """Record a failure status for the run."""

        self._close(status=status)

    def _close(self, *, status: str) -> None:
        if self._closed:
            return

        elapsed = perf_counter() - self._started_at
        CALL_EXPORT_RUNS_TOTAL.labels(status=status).inc()
        CALL_EXPORT_DURATION_SECONDS.labels(status=status).observe(elapsed)
        self._closed = True

    def __enter__(self) -> "CallExportRunTracker":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.mark_completed()
        else:
            self.mark_failed()
        return False


def record_call_export_retry(stage: str, *, reason: str = "retry") -> None:
    """Increment the retry counter for a given workflow stage."""

    CALL_EXPORT_RETRY_TOTAL.labels(stage=stage, reason=reason).inc()


def record_call_export_dlq(stage: str, *, reason: str | None = None) -> None:
    """Increment the DLQ counter for the provided stage and reason."""

    CALL_EXPORT_DLQ_TOTAL.labels(stage=stage, reason=reason or "unknown").inc()


__all__ = [
    "CallExportRunTracker",
    "record_call_export_dlq",
    "record_call_export_retry",
]
