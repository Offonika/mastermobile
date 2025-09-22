import pytest

import httpx

BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_health() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.get("/health")
        ping_response = await client.get("/api/v1/system/ping")

    assert response.status_code == 200
    assert response.json().get("status") == "ok"

    assert ping_response.status_code == 200
    payload = ping_response.json()
    assert payload["status"] == "pong"
    assert "timestamp" in payload
    assert payload["checks"].get("database") == "ok"
