"""System-level API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...api.dependencies import inject_request_id
from ...api.schemas.returns import Error, Ping
from ...db.session import get_session

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get(
    "/ping",
    response_model=Ping,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": Error}},
)
def ping(
    *,
    request_id: str = Depends(inject_request_id),
    session: Session = Depends(get_session),
) -> Ping:
    """Return the current availability status of the middleware."""

    checks: dict[str, str] = {}

    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:  # pragma: no cover - defensive branch
        checks["database"] = "error"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=Error(
                type="about:blank",
                title="Service unavailable",
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection check failed.",
                request_id=request_id,
            ).model_dump(exclude_none=True),
        ) from exc
    else:
        checks["database"] = "ok"

    timestamp = datetime.now(timezone.utc)
    return Ping(status="pong", timestamp=timestamp, service="mastermobile-mw", checks=checks)
