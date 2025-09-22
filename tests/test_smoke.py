"""Smoke tests ensuring primary endpoints respond successfully."""

import httpx
import pytest

from apps.mw.src.app import app

BASE_URL = "http://testserver"


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"
    assert "X-Request-Id" in response.headers


@pytest.mark.asyncio
async def test_system_ping_returns_status_and_timestamp() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.get("/api/v1/system/ping")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "pong"
    assert "timestamp" in payload
    assert response.headers.get("X-Request-Id")
