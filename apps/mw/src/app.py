"""FastAPI application setup and router registration."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from apps.mw.src.api.dependencies import (
    ProblemDetailException,
    build_error,
    provide_request_id,
)
from apps.mw.src.api.routes import call_registry as call_registry_router
from apps.mw.src.api.routes import returns as returns_router
from apps.mw.src.api.routes import system as system_router
from apps.mw.src.api.schemas import Error, Health
from apps.mw.src.health import get_health_payload

app = FastAPI(title="MasterMobile MW")

app.include_router(system_router.router)
app.include_router(call_registry_router.router)
app.include_router(returns_router.router)


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
    request_id = error.request_id or request.headers.get("X-Request-Id") or str(uuid4())
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

    request_id = request.headers.get("X-Request-Id") or str(uuid4())
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
