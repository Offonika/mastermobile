"""System level API endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from apps.mw.src.api.dependencies import provide_request_id
from apps.mw.src.api.schemas import Ping

router = APIRouter(
    prefix="/api/v1/system",
    tags=["system"],
    dependencies=[Depends(provide_request_id)],
)


@router.get("/ping", response_model=Ping, summary="Ping the middleware")
async def ping() -> Ping:
    """Return a basic heartbeat payload with current UTC timestamp."""

    return Ping(
        status="pong",
        timestamp=datetime.now(timezone.utc),
        service="master-mobile-middleware",
    )
