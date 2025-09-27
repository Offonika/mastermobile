"""Prometheus metrics exposure endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client.exposition import generate_latest

router = APIRouter(tags=["metrics"])


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Return middleware metrics in Prometheus exposition format."""

    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
