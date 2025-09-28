"""Prometheus metrics helpers for the middleware services."""
from __future__ import annotations

from time import perf_counter
from typing import Final

from fastapi import FastAPI, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

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

HTTP_REQUESTS_TOTAL: Final[Counter] = Counter(
    "http_requests_total",
    "Total number of HTTP requests processed by the middleware service.",
    labelnames=("method", "status_code", "path"),
)
"""Counter that tracks processed HTTP requests broken down by route."""

HTTP_REQUEST_DURATION_SECONDS: Final[Histogram] = Histogram(
    "http_request_duration_seconds",
    "Histogram of HTTP request latency in seconds.",
    labelnames=("method", "status_code", "path"),
)
"""Histogram measuring HTTP server latency distribution."""

CALL_EXPORT_RUNS_TOTAL: Final[Counter] = Counter(
    "call_export_runs_total",
    "Total number of Bitrix24 call export runs grouped by status.",
    labelnames=("status",),
)
"""Counter tracking lifecycle outcomes for full call export runs."""

CALL_EXPORT_DURATION_SECONDS: Final[Histogram] = Histogram(
    "call_export_duration_seconds",
    "Histogram of Bitrix24 call export stage durations in seconds.",
    labelnames=("stage", "status"),
)
"""Histogram measuring how long individual call export stages take."""

CALL_TRANSCRIPTS_TOTAL: Final[Counter] = Counter(
    "call_transcripts_total",
    "Total number of call transcripts processed by outcome and STT engine.",
    labelnames=("status", "engine"),
)
"""Counter recording transcription attempts and their results."""

CALL_TRANSCRIPTION_MINUTES_TOTAL: Final[Counter] = Counter(
    "call_transcription_minutes_total",
    "Accumulated transcription duration in minutes grouped by engine.",
    labelnames=("engine",),
)
"""Counter summarising the amount of audio transcribed in minutes."""

CALL_EXPORT_COST_TOTAL: Final[Counter] = Counter(
    "call_export_cost_total",
    "Total transcription cost reported by currency code.",
    labelnames=("currency",),
)
"""Counter that aggregates transcription spend for budgeting alerts."""

CALL_EXPORT_RETRY_TOTAL: Final[Counter] = Counter(
    "call_export_retry_total",
    "Total number of retries performed across call export stages.",
    labelnames=("stage",),
)
"""Counter used to monitor retry storms in downstream integrations."""

CALL_EXPORT_QA_CHECKED_TOTAL: Final[Counter] = Counter(
    "call_export_qa_checked_total",
    "Number of transcripts reviewed by QA grouped by verdict.",
    labelnames=("result",),
)
"""Counter tracking the manual QA coverage of transcripts."""

CALL_EXPORT_TRANSCRIBE_FAILURES_TOTAL: Final[Counter] = Counter(
    "call_export_transcribe_failures_total",
    "Total transcription failures observed grouped by status code.",
    labelnames=("code",),
)
"""Counter surfacing Whisper/STT failure codes for alerting."""

CALL_EXPORT_REPORTS_TOTAL: Final[Counter] = Counter(
    "call_export_reports_total",
    "Number of call export registry reports downloaded grouped by format.",
    labelnames=("format",),
)
"""Counter measuring demand for registry CSV exports and other formats."""


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Collect per-request Prometheus metrics for the FastAPI application."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> StarletteResponse:
        start_time = perf_counter()
        status_code = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            raise
        finally:
            elapsed = perf_counter() - start_time
            route = request.scope.get("route")
            path_template = getattr(route, "path", request.url.path)
            labels = (
                request.method,
                str(status_code or status.HTTP_500_INTERNAL_SERVER_ERROR),
                path_template,
            )
            HTTP_REQUESTS_TOTAL.labels(*labels).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(*labels).observe(elapsed)


def register_metrics(app: FastAPI) -> None:
    """Attach the Prometheus `/metrics` endpoint to the FastAPI application."""

    @app.get("/metrics")
    async def metrics_endpoint() -> Response:  # pragma: no cover - exercised in integration
        payload = generate_latest()
        return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


__all__ = [
    "CALL_EXPORT_COST_TOTAL",
    "CALL_EXPORT_DURATION_SECONDS",
    "CALL_EXPORT_QA_CHECKED_TOTAL",
    "CALL_EXPORT_REPORTS_TOTAL",
    "CALL_EXPORT_RETRY_TOTAL",
    "CALL_EXPORT_RUNS_TOTAL",
    "CALL_EXPORT_TRANSCRIBE_FAILURES_TOTAL",
    "CALL_TRANSCRIPTION_MINUTES_TOTAL",
    "CALL_TRANSCRIPTS_TOTAL",
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_DURATION_SECONDS",
    "RequestMetricsMiddleware",
    "STT_JOBS_TOTAL",
    "STT_JOB_DURATION_SECONDS",
    "register_metrics",
]
