"""Task runner helpers for Bitrix24 call export jobs."""
from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from apps.mw.src.db.models import CallExportStatus
from apps.mw.src.observability.metrics import (
    CALL_EXPORT_DURATION_SECONDS,
    CALL_EXPORT_RETRY_TOTAL,
    CALL_EXPORT_RUNS_TOTAL,
)

__all__ = ["CallExportCallable", "run_call_export"]


CallExportCallable = Callable[[], CallExportStatus | None]
"""Callable executed to perform a single call export run."""


def run_call_export(
    task: CallExportCallable,
    *,
    max_retries: int = 0,
    retry_exceptions: Sequence[type[BaseException]] | None = None,
) -> CallExportStatus:
    """Execute the call export task while emitting Prometheus metrics."""

    allowed_exceptions: tuple[type[BaseException], ...]
    if retry_exceptions is None:
        allowed_exceptions = (Exception,)
    else:
        allowed_exceptions = tuple(retry_exceptions)
        if not allowed_exceptions:
            raise ValueError("retry_exceptions must not be empty")

    attempts = 0
    status = CallExportStatus.IN_PROGRESS
    start = time.perf_counter()

    try:
        while True:
            try:
                result = task()
            except allowed_exceptions:
                attempts += 1
                if attempts > max_retries:
                    status = CallExportStatus.ERROR
                    raise
                CALL_EXPORT_RETRY_TOTAL.inc()
                continue

            status = (
                result
                if isinstance(result, CallExportStatus)
                else CallExportStatus.COMPLETED
            )
            break
    except Exception:
        status = CallExportStatus.ERROR
        raise
    finally:
        duration = max(time.perf_counter() - start, 0.0)
        CALL_EXPORT_DURATION_SECONDS.observe(duration)
        CALL_EXPORT_RUNS_TOTAL.labels(status=status.value).inc()

    return status
