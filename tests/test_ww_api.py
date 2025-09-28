"""Integration tests for Walking Warehouse API endpoints."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from apps.mw.src.app import app
from apps.mw.src.api.dependencies import reset_idempotency_cache
from apps.mw.src.api.routes.ww import get_courier_repository, get_order_repository
from apps.mw.src.integrations.ww import (
    WalkingWarehouseCourierRepository,
    WalkingWarehouseOrderRepository,
)

BASE_URL = "http://testserver"


@pytest.fixture(autouse=True)
def _reset_idempotency() -> None:
    reset_idempotency_cache()
    yield
    reset_idempotency_cache()


@pytest.fixture(autouse=True)
def override_repositories() -> None:
    courier_repo = WalkingWarehouseCourierRepository()
    order_repo = WalkingWarehouseOrderRepository()
    app.dependency_overrides[get_courier_repository] = lambda: courier_repo
    app.dependency_overrides[get_order_repository] = lambda: order_repo
    yield
    app.dependency_overrides.pop(get_courier_repository, None)
    app.dependency_overrides.pop(get_order_repository, None)


@pytest_asyncio.fixture()
async def api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        yield client


def _courier_payload(courier_id: str = "courier-1", **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": courier_id,
        "display_name": "John Doe",
        "phone": "+79001002030",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _order_payload(order_id: str | None = None, courier_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": order_id,
        "title": "Grocery delivery",
        "customer_name": "Alice",
        "status": "NEW",
        "courier_id": courier_id,
        "currency_code": "RUB",
        "total_amount": "990.50",
        "notes": "Deliver before 18:00",
        "items": [
            {
                "sku": "SKU-100",
                "name": "Coffee",
                "qty": 2,
                "price": "250.00",
            },
            {
                "sku": "SKU-200",
                "name": "Cookies",
                "qty": 1,
                "price": "490.50",
            },
        ],
    }
    payload.update(overrides)
    return payload


async def _create_courier(client: httpx.AsyncClient, courier_id: str = "courier-1") -> httpx.Response:
    headers = {"Idempotency-Key": f"courier-{uuid4()}"}
    return await client.post("/api/v1/ww/couriers", json=_courier_payload(courier_id), headers=headers)


async def _create_order(
    client: httpx.AsyncClient,
    order_id: str | None = None,
    courier_id: str | None = None,
    idempotency_key: str | None = None,
) -> httpx.Response:
    headers = {"Idempotency-Key": idempotency_key or f"order-{uuid4()}"}
    return await client.post(
        "/api/v1/ww/orders",
        json=_order_payload(order_id=order_id, courier_id=courier_id),
        headers=headers,
    )


@pytest.mark.asyncio
async def test_courier_creation_and_listing(api_client: httpx.AsyncClient) -> None:
    response = await _create_courier(api_client, "courier-101")
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "courier-101"
    assert response.headers["Location"].endswith("courier-101")

    list_response = await api_client.get("/api/v1/ww/couriers")
    assert list_response.status_code == 200
    couriers = list_response.json()["items"]
    assert any(courier["id"] == "courier-101" for courier in couriers)


@pytest.mark.asyncio
async def test_order_lifecycle_happy_path(api_client: httpx.AsyncClient) -> None:
    await _create_courier(api_client, "courier-201")
    await _create_courier(api_client, "courier-202")

    create_response = await _create_order(api_client, courier_id="courier-201")
    assert create_response.status_code == 201
    order = create_response.json()
    order_id = order["id"]
    assert order["courier_id"] == "courier-201"
    assert order["status"] == "NEW"

    list_response = await api_client.get(
        "/api/v1/ww/orders",
        params=[("status", "NEW"), ("q", "grocery")],
    )
    assert list_response.status_code == 200
    orders = list_response.json()["items"]
    assert any(item["id"] == order_id for item in orders)

    patch_headers = {"Idempotency-Key": f"patch-{uuid4()}"}
    patch_payload = {
        "title": "Updated grocery delivery",
        "customer_name": "Alice Smith",
        "currency_code": "RUB",
        "total_amount": "1000.50",
        "items": [
            {
                "sku": "SKU-100",
                "name": "Coffee",
                "qty": 3,
                "price": "250.00",
            }
        ],
    }
    patch_response = await api_client.patch(
        f"/api/v1/ww/orders/{order_id}", json=patch_payload, headers=patch_headers
    )
    assert patch_response.status_code == 200
    updated = patch_response.json()
    assert updated["title"] == "Updated grocery delivery"
    assert updated["items"][0]["qty"] == 3

    assign_headers = {"Idempotency-Key": f"assign-{uuid4()}"}
    assign_response = await api_client.post(
        f"/api/v1/ww/orders/{order_id}/assign",
        json={"courier_id": "courier-202"},
        headers=assign_headers,
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["courier_id"] == "courier-202"
    assert assign_response.json()["status"] == "ASSIGNED"

    status_headers = {"Idempotency-Key": f"status-{uuid4()}"}
    status_response = await api_client.post(
        f"/api/v1/ww/orders/{order_id}/status",
        json={"status": "IN_TRANSIT"},
        headers=status_headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "IN_TRANSIT"

    done_headers = {"Idempotency-Key": f"done-{uuid4()}"}
    done_response = await api_client.post(
        f"/api/v1/ww/orders/{order_id}/status",
        json={"status": "DONE"},
        headers=done_headers,
    )
    assert done_response.status_code == 200
    assert done_response.json()["status"] == "DONE"


@pytest.mark.asyncio
async def test_error_scenarios(api_client: httpx.AsyncClient) -> None:
    await _create_courier(api_client, "courier-301")
    duplicate_response = await _create_courier(api_client, "courier-301")
    assert duplicate_response.status_code == 409

    create_order_response = await _create_order(api_client, courier_id="missing-courier")
    assert create_order_response.status_code == 404

    missing_idempotency = await api_client.post(
        "/api/v1/ww/orders",
        json=_order_payload(courier_id="courier-301"),
    )
    assert missing_idempotency.status_code == 422
    assert missing_idempotency.json()["title"] == "Invalid Idempotency-Key header"

    headers = {"Idempotency-Key": f"update-{uuid4()}"}
    update_missing = await api_client.patch(
        f"/api/v1/ww/orders/{uuid4()}", json={"title": "noop"}, headers=headers
    )
    assert update_missing.status_code == 404


@pytest.mark.asyncio
async def test_create_order_replay_returns_cached_response(
    api_client: httpx.AsyncClient,
) -> None:
    await _create_courier(api_client, "courier-401")

    idempotency_key = "order-repeat-key"
    payload = _order_payload(courier_id="courier-401")

    first_response = await api_client.post(
        "/api/v1/ww/orders",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert first_response.status_code == 201
    first_body = first_response.json()

    second_response = await api_client.post(
        "/api/v1/ww/orders",
        json=payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    assert second_response.status_code == 200
    assert second_response.json() == first_body
    assert second_response.headers.get("Location") == first_response.headers.get("Location")

    list_response = await api_client.get("/api/v1/ww/orders")
    orders = list_response.json()["items"]
    assert len(orders) == 1
    assert orders[0]["id"] == first_body["id"]

    assign_headers = {"Idempotency-Key": f"assign-{uuid4()}"}
    assign_response = await api_client.post(
        f"/api/v1/ww/orders/{uuid4()}/assign",
        json={"courier_id": "courier-301"},
        headers=assign_headers,
    )
    assert assign_response.status_code == 404

    assign_headers_existing = {"Idempotency-Key": f"assign-{uuid4()}"}
    order_id = (await _create_order(api_client, courier_id="courier-301")).json()["id"]
    assign_missing_courier = await api_client.post(
        f"/api/v1/ww/orders/{order_id}/assign",
        json={"courier_id": "unknown"},
        headers=assign_headers_existing,
    )
    assert assign_missing_courier.status_code == 404

    status_headers = {"Idempotency-Key": f"status-{uuid4()}"}
    status_missing = await api_client.post(
        f"/api/v1/ww/orders/{uuid4()}/status",
        json={"status": "IN_TRANSIT"},
        headers=status_headers,
    )
    assert status_missing.status_code == 404


@pytest.mark.asyncio
async def test_invalid_status_transition_returns_422(api_client: httpx.AsyncClient) -> None:
    await _create_courier(api_client, "courier-401")
    order_id = (await _create_order(api_client, courier_id="courier-401")).json()["id"]

    status_headers = {"Idempotency-Key": f"status-{uuid4()}"}
    invalid_transition = await api_client.post(
        f"/api/v1/ww/orders/{order_id}/status",
        json={"status": "DONE"},
        headers=status_headers,
    )
    assert invalid_transition.status_code == 422
    body = invalid_transition.json()
    assert body["title"] == "Invalid order status transition"


@pytest.mark.asyncio
async def test_assignment_decline_resets_order_status(api_client: httpx.AsyncClient) -> None:
    await _create_courier(api_client, "courier-501")
    order_id = (await _create_order(api_client, courier_id="courier-501")).json()["id"]

    assign_headers = {"Idempotency-Key": f"assign-{uuid4()}"}
    assign_response = await api_client.post(
        f"/api/v1/ww/orders/{order_id}/assign",
        json={"courier_id": "courier-501"},
        headers=assign_headers,
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["status"] == "ASSIGNED"

    decline_headers = {"Idempotency-Key": f"decline-{uuid4()}"}
    decline_response = await api_client.post(
        f"/api/v1/ww/orders/{order_id}/assign",
        json={"courier_id": None, "decline": True},
        headers=decline_headers,
    )
    assert decline_response.status_code == 200
    declined_body = decline_response.json()
    assert declined_body["courier_id"] is None
    assert declined_body["status"] == "NEW"


@pytest.mark.asyncio
async def test_decline_without_assignment_returns_422(api_client: httpx.AsyncClient) -> None:
    await _create_courier(api_client, "courier-601")
    order_id = (await _create_order(api_client)).json()["id"]

    decline_headers = {"Idempotency-Key": f"decline-{uuid4()}"}
    decline_response = await api_client.post(
        f"/api/v1/ww/orders/{order_id}/assign",
        json={"courier_id": None, "decline": True},
        headers=decline_headers,
    )
    assert decline_response.status_code == 422
    body = decline_response.json()
    assert body["title"] == "Invalid assignment state"
