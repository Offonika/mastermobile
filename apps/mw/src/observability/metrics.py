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

CALL_EXPORT_RUNS_TOTAL: Final[Counter] = Counter(
    "call_export_runs_total",
    "Total number of call export runs executed grouped by final status.",
    labelnames=("status",),
)
"""Counter that records how many call export runs reached each status."""

CALL_EXPORT_DURATION_SECONDS: Final[Histogram] = Histogram(
    "call_export_duration_seconds",
    "Histogram of call export run durations in seconds grouped by final status.",
    labelnames=("status",),
)
"""Histogram that captures the run time of call export executions."""

CALL_EXPORT_DOWNLOADS_TOTAL: Final[Counter] = Counter(
    "call_export_downloads_total",
    "Total number of call recording download attempts grouped by outcome.",
    labelnames=("status",),
)
"""Counter tracking download attempts for Bitrix24 call recordings."""

CALL_EXPORT_DOWNLOAD_DURATION_SECONDS: Final[Histogram] = Histogram(
    "call_export_download_duration_seconds",
    "Histogram of call recording download durations in seconds grouped by outcome.",
    labelnames=("status",),
)
"""Histogram measuring download latency for Bitrix24 recordings."""

CALL_EXPORT_RETRY_TOTAL: Final[Counter] = Counter(
    "call_export_retry_total",
    "Total number of retry attempts performed by the call export workflow.",
    labelnames=("stage", "reason"),
)
"""Counter that records retry activity across call export workflow stages."""

CALL_EXPORT_DLQ_TOTAL: Final[Counter] = Counter(
    "call_export_dlq_total",
    "Total number of call export workflow items moved to the DLQ.",
    labelnames=("stage", "reason"),
)
"""Counter capturing DLQ escalations within the call export workflow."""

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
    "CALL_EXPORT_DLQ_TOTAL",
    "CALL_EXPORT_DOWNLOADS_TOTAL",
    "CALL_EXPORT_DOWNLOAD_DURATION_SECONDS",
    "CALL_EXPORT_DURATION_SECONDS",
    "CALL_EXPORT_RETRY_TOTAL",
    "CALL_EXPORT_RUNS_TOTAL",
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_DURATION_SECONDS",
    "RequestMetricsMiddleware",
    "STT_JOBS_TOTAL",
    "STT_JOB_DURATION_SECONDS",
    "register_metrics",
]
