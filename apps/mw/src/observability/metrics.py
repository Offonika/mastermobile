"""Prometheus metric definitions used across the middleware."""
from __future__ import annotations

from prometheus_client import Counter, Histogram

__all__ = [
    "CALL_EXPORT_RUNS_TOTAL",
    "CALL_EXPORT_DURATION_SECONDS",
    "CALL_EXPORT_RETRY_TOTAL",
    "reset_call_export_metrics",
]


CALL_EXPORT_RUNS_TOTAL = Counter(
    "call_export_runs_total",
    "Total number of call export runs partitioned by final status.",
    labelnames=("status",),
)
"""Counter of call export runs grouped by their terminal status."""


CALL_EXPORT_DURATION_SECONDS = Histogram(
    "call_export_duration_seconds",
    "Observed duration of call export runs in seconds.",
    buckets=(
        30.0,
        60.0,
        120.0,
        300.0,
        600.0,
        1200.0,
        3600.0,
        7200.0,
    ),
)
"""Histogram capturing how long call export runs take to finish."""


CALL_EXPORT_RETRY_TOTAL = Counter(
    "call_export_retry_total",
    "Total number of retry attempts performed by the call export job.",
)
"""Counter tracking how many retry attempts were executed within call exports."""


def reset_call_export_metrics() -> None:
    """Reset call export metric series to zero values (used in tests)."""

    CALL_EXPORT_RUNS_TOTAL._metrics.clear()
    if hasattr(CALL_EXPORT_RETRY_TOTAL, "_value"):
        CALL_EXPORT_RETRY_TOTAL._value.set(0)

    for bucket in getattr(CALL_EXPORT_DURATION_SECONDS, "_buckets", []):
        bucket.set(0)
    if hasattr(CALL_EXPORT_DURATION_SECONDS, "_sum"):
        CALL_EXPORT_DURATION_SECONDS._sum.set(0)
