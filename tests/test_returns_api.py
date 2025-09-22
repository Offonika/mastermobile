"""Integration tests covering the returns API surface."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

BASE_URL = "http://localhost:8000"


def _sample_payload(line_suffix: str = "1") -> dict[str, object]:
    return {
        "source": "warehouse",
        "courier_id": "courier-99",
        "comment": "Initial pickup",
        "items": [
            {
                "line_id": f"line-{line_suffix}",
                "sku": f"SKU-{line_suffix}",
                "qty": "1.000",
                "quality": "new",
                "reason_id": None,
            }
        ],
    }


@pytest.mark.asyncio
async def test_returns_crud_flow() -> None:
    idempotency_key = str(uuid4())

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        create_response = await client.post(
            "/api/v1/returns",
            json=_sample_payload(),
            headers={"Idempotency-Key": idempotency_key},
        )

        assert create_response.status_code == 201
        created = create_response.json()
        return_id = created["id"]
        assert created["items"][0]["sku"] == "SKU-1"
        assert "X-Request-Id" in create_response.headers
        assert create_response.headers["Location"].endswith(return_id)

        list_response = await client.get("/api/v1/returns")
        assert list_response.status_code == 200
        listing = list_response.json()
        assert listing["total_items"] == 1
        assert listing["items"][0]["id"] == return_id

        detail_response = await client.get(f"/api/v1/returns/{return_id}")
        assert detail_response.status_code == 200
        assert detail_response.json()["id"] == return_id

        update_payload = _sample_payload("2")
        update_payload["status"] = "accepted"
        update_response = await client.put(
            f"/api/v1/returns/{return_id}",
            json=update_payload,
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert update_response.status_code == 200
        assert update_response.json()["items"][0]["sku"] == "SKU-2"
        assert update_response.json()["status"] == "accepted"

        delete_response = await client.delete(
            f"/api/v1/returns/{return_id}",
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert delete_response.status_code == 204

        missing_response = await client.get(f"/api/v1/returns/{return_id}")
        assert missing_response.status_code == 404
        assert missing_response.json()["detail"]["status"] == 404


@pytest.mark.asyncio
async def test_idempotency_conflict_on_mismatched_payload() -> None:
    key = str(uuid4())

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        first = await client.post(
            "/api/v1/returns",
            json=_sample_payload(),
            headers={"Idempotency-Key": key},
        )
        assert first.status_code == 201

        payload = _sample_payload("conflict")
        payload["comment"] = "changed"
        second = await client.post(
            "/api/v1/returns",
            json=payload,
            headers={"Idempotency-Key": key},
        )

        assert second.status_code == 409
        body = second.json()
        assert body["detail"]["status"] == 409
        assert "Payload differs" in body["detail"]["detail"]


@pytest.mark.asyncio
async def test_operations_require_idempotency_key() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.post("/api/v1/returns", json=_sample_payload())
        assert response.status_code == 422

        created = await client.post(
            "/api/v1/returns",
            json=_sample_payload(),
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert created.status_code == 201
        return_id = created.json()["id"]

        update_response = await client.put(
            f"/api/v1/returns/{return_id}",
            json=_sample_payload("updated"),
        )
        assert update_response.status_code == 422

        delete_response = await client.delete(f"/api/v1/returns/{return_id}")
        assert delete_response.status_code == 422
