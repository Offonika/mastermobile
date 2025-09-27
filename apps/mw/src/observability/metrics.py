"""Prometheus metrics helpers for the middleware services."""
from __future__ import annotations

from typing import Final

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

STT_JOBS_TOTAL: Final[Counter] = Counter(
    "stt_jobs_total",
    "Total number of STT jobs handled by the worker, labelled by final status.",
    labelnames=("status",),
)
"""Global counter that tracks STT job outcomes."""

STT_JOB_DURATION_SECONDS: Final[Histogram] = Histogram(
    "stt_job_duration_seconds",
    "Histogram of end-to-end STT job processing time in seconds.",
)
"""Histogram that records how long a job spent in the worker pipeline."""


def register_metrics(app: FastAPI) -> None:
    """Attach the Prometheus `/metrics` endpoint to the FastAPI application."""

    @app.get("/metrics")
    async def metrics_endpoint() -> Response:  # pragma: no cover - exercised in integration
        payload = generate_latest()
        return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


__all__ = ["STT_JOBS_TOTAL", "STT_JOB_DURATION_SECONDS", "register_metrics"]
