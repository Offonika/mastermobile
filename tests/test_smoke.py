from datetime import UTC, datetime, timedelta

import pytest

import httpx

BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_health() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


@pytest.mark.asyncio
async def test_system_ping() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.get("/api/v1/system/ping")

    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "pong"

    timestamp = payload["timestamp"]
    parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    assert parsed_timestamp.tzinfo is not None
    assert parsed_timestamp.tzinfo.utcoffset(parsed_timestamp) == timedelta(0)

    now = datetime.now(UTC)
    delta = now - parsed_timestamp
    assert timedelta(0) <= delta < timedelta(seconds=5)

    if "service" in payload:
        assert isinstance(payload["service"], str)
        assert payload["service"].strip()
