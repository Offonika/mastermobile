import pytest

import httpx

BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_health() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"
