"""FastAPI application setup and router registration."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from apps.mw.src.api.dependencies import (
    ProblemDetailException,
    build_error,
    provide_request_id,
)
from apps.mw.src.config import get_settings
from apps.mw.src.api.routes import b24_calls as b24_calls_router
from apps.mw.src.api.routes import call_registry as call_registry_router
from apps.mw.src.api.routes import chatkit as chatkit_routes_router
from apps.mw.src.api.routes import returns as returns_router
from apps.mw.src.api.routes import stt_admin as stt_admin_router
from apps.mw.src.api.routes import system as system_router
from apps.mw.src.api.routes import ww as ww_router
from apps.mw.src.api.routers import chatkit as chatkit_router
from apps.mw.src.api.schemas import Error, Health
from apps.mw.src.health import get_health_payload
from apps.mw.src.observability import (
    RequestContextMiddleware,
    RequestMetricsMiddleware,
    create_logging_lifespan,
    register_metrics,
)
from apps.mw.src.services.cleanup import StorageCleanupRunner
from apps.mw.src.services.storage import StorageService

app = FastAPI(title="MasterMobile MW", lifespan=create_logging_lifespan())
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RequestMetricsMiddleware)
register_metrics(app)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router.router)
app.include_router(b24_calls_router.router)
app.include_router(call_registry_router.router)
app.include_router(returns_router.router)
app.include_router(stt_admin_router.router)
app.include_router(ww_router.router)
app.include_router(chatkit_routes_router.router)
app.include_router(chatkit_router.router)


@app.on_event("startup")
async def start_background_jobs() -> None:
    """Initialise background tasks that run for the app lifespan."""

    settings = get_settings()
    storage_service = StorageService(settings=settings)
    cleanup_runner = StorageCleanupRunner(storage_service=storage_service, settings=settings)
    task = asyncio.create_task(cleanup_runner.run_periodic(), name="storage-cleanup")
    app.state.storage_cleanup_runner = cleanup_runner
    app.state.storage_cleanup_task = task


@app.on_event("shutdown")
async def stop_background_jobs() -> None:
    """Cancel background tasks before shutting down the application."""

    task = getattr(app.state, "storage_cleanup_task", None)
    if task is None:
        return

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


@app.get("/health", response_model=Health)
async def health(response: Response, request_id: str = Depends(provide_request_id)) -> Health:
    """Simple health-check endpoint used by smoke tests."""

    payload = get_health_payload()
    if isinstance(payload, Health):
        return payload
    if isinstance(payload, dict):
        payload = Health.model_validate(payload)
    return payload


@app.exception_handler(ProblemDetailException)
async def handle_problem_detail(request: Request, exc: ProblemDetailException) -> JSONResponse:
    """Render RFC7807 responses raised by dependencies and routes."""

    error = exc.error
    request_id = (
        error.request_id
        or getattr(request.state, "request_id", None)
        or request.headers.get("X-Request-Id")
        or str(uuid4())
    )
    error = Error(**{**error.model_dump(exclude_none=True), "request_id": request_id})
    response = JSONResponse(
        status_code=error.status,
        content=error.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert FastAPI validation errors into problem details responses."""

    request_id = (
        getattr(request.state, "request_id", None)
        or request.headers.get("X-Request-Id")
        or str(uuid4())
    )
    errors: list[dict[str, Any]] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", []) if part not in {"body"})
        errors.append({
            "field": loc or "body",
            "message": error.get("msg", "Invalid value."),
        })

    problem = build_error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Validation failed",
        detail="Request validation failed.",
        request_id=request_id,
        type_="https://api.mastermobile.app/errors/validation",
        errors=errors or None,
    )

    response = JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )
    response.headers["X-Request-Id"] = request_id
    return response
