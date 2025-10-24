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

WW_EXPORT_ATTEMPTS_TOTAL: Final[Counter] = Counter(
    "ww_export_attempts_total",
    "Number of Walking Warehouse export operations that were attempted.",
    labelnames=("operation",),
)
"""Counter tracking how often each Walking Warehouse export handler runs."""

WW_EXPORT_SUCCESS_TOTAL: Final[Counter] = Counter(
    "ww_export_success_total",
    "Number of Walking Warehouse export operations that completed successfully.",
    labelnames=("operation",),
)
"""Counter tracking successful Walking Warehouse export handler executions."""

WW_EXPORT_FAILURE_TOTAL: Final[Counter] = Counter(
    "ww_export_failure_total",
    "Number of Walking Warehouse export operations that failed.",
    labelnames=("operation", "reason"),
)
"""Counter tracking failed Walking Warehouse export handler executions grouped by reason."""

WW_EXPORT_DURATION_SECONDS: Final[Histogram] = Histogram(
    "ww_export_duration_seconds",
    "Histogram of Walking Warehouse export handler execution time in seconds.",
    labelnames=("operation", "outcome"),
)
"""Histogram tracking latency of Walking Warehouse export handlers by outcome."""

WW_ORDER_STATUS_TRANSITIONS_TOTAL: Final[Counter] = Counter(
    "ww_order_status_transitions_total",
    "Number of Walking Warehouse order status transitions processed.",
    labelnames=("from_status", "to_status", "result"),
)
"""Counter monitoring Walking Warehouse order status transition attempts and outcomes."""

WW_KMP4_EXPORTS_TOTAL: Final[Counter] = Counter(
    "ww_kmp4_exports_total",
    "Total number of Walking Warehouse KMP4 exports grouped by outcome.",
    labelnames=("status",),
)
"""Counter summarising KMP4 export outcomes exposed on the default registry."""


class WWExportTracker:
    """Helper recording Prometheus metrics for Walking Warehouse export operations."""

    __slots__ = ("_operation", "_started", "_completed")

    def __init__(self, operation: str) -> None:
        self._operation = operation
        self._started = perf_counter()
        self._completed = False
        WW_EXPORT_ATTEMPTS_TOTAL.labels(operation=operation).inc()

    def success(self) -> None:
        """Record a successful export execution."""

        if self._completed:
            return
        elapsed = perf_counter() - self._started
        WW_EXPORT_SUCCESS_TOTAL.labels(operation=self._operation).inc()
        WW_EXPORT_DURATION_SECONDS.labels(
            operation=self._operation, outcome="success"
        ).observe(elapsed)
        self._completed = True

    def failure(self, reason: str) -> None:
        """Record a failed export execution with the provided reason."""

        if self._completed:
            return
        elapsed = perf_counter() - self._started
        WW_EXPORT_FAILURE_TOTAL.labels(
            operation=self._operation, reason=reason
        ).inc()
        if self._operation == "kmp4_export":
            WW_KMP4_EXPORTS_TOTAL.labels(status="error").inc()
        WW_EXPORT_DURATION_SECONDS.labels(
            operation=self._operation, outcome="failure"
        ).observe(elapsed)
        self._completed = True


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
    "WW_EXPORT_ATTEMPTS_TOTAL",
    "WW_EXPORT_SUCCESS_TOTAL",
    "WW_EXPORT_FAILURE_TOTAL",
    "WW_EXPORT_DURATION_SECONDS",
    "WW_KMP4_EXPORTS_TOTAL",
    "WW_ORDER_STATUS_TRANSITIONS_TOTAL",
    "WWExportTracker",
    "register_metrics",
]
