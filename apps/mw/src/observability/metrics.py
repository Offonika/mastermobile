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
    "HTTP_REQUESTS_TOTAL",
    "HTTP_REQUEST_DURATION_SECONDS",
    "RequestMetricsMiddleware",
    "STT_JOBS_TOTAL",
    "STT_JOB_DURATION_SECONDS",
    "register_metrics",
]
