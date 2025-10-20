from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio

import httpx
from apps.mw.src.api.dependencies import reset_idempotency_cache
from apps.mw.src.api.routes.ww import (
    get_courier_repository,
    get_order_repository,
)
from apps.mw.src.api.schemas import WWOrderStatus
from apps.mw.src.app import app
from apps.mw.src.integrations.ww import (
    OrderItemRecord,
    WalkingWarehouseCourierRepository,
    WalkingWarehouseOrderRepository,
)

BASE_URL = "http://testserver"


@pytest.fixture(autouse=True)
def _reset_idempotency() -> None:
    reset_idempotency_cache()
    yield
    reset_idempotency_cache()


@pytest.fixture()
def ww_repositories() -> tuple[WalkingWarehouseCourierRepository, WalkingWarehouseOrderRepository]:
    courier_repo = WalkingWarehouseCourierRepository()
    order_repo = WalkingWarehouseOrderRepository()
    app.dependency_overrides[get_courier_repository] = lambda: courier_repo
    app.dependency_overrides[get_order_repository] = lambda: order_repo
    yield courier_repo, order_repo
    app.dependency_overrides.pop(get_courier_repository, None)
    app.dependency_overrides.pop(get_order_repository, None)


@pytest_asyncio.fixture()
async def api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        yield client


def _seed_order(
    order_repo: WalkingWarehouseOrderRepository,
    *,
    order_id: str,
    courier_id: str | None,
    status: WWOrderStatus,
    created_at: datetime,
    updated_at: datetime,
    total_amount: Decimal,
) -> None:
    payload = order_repo.create(
        order_id=order_id,
        title=f"Delivery {order_id}",
        customer_name="Alice",
        status=status.value,
        courier_id=courier_id,
        currency_code="RUB",
        total_amount=total_amount,
        notes="Handle with care",
        items=[
            OrderItemRecord(
                sku=f"SKU-{order_id}",
                name="Coffee",
                qty=1,
                price=total_amount,
            )
        ],
    )
    payload.created_at = created_at
    payload.updated_at = updated_at


@pytest.mark.asyncio
async def test_delivery_report_json_and_csv(
    api_client: httpx.AsyncClient,
    ww_repositories: tuple[WalkingWarehouseCourierRepository, WalkingWarehouseOrderRepository],
) -> None:
    courier_repo, order_repo = ww_repositories
    courier_repo.create(
        courier_id="courier-1",
        display_name="Courier One",
        phone="+79000000001",
        is_active=True,
    )
    courier_repo.create(
        courier_id="courier-2",
        display_name="Courier Two",
        phone="+79000000002",
        is_active=True,
    )

    start = datetime(2024, 1, 1, 9, 0, tzinfo=datetime.UTC)
    _seed_order(
        order_repo,
        order_id="order-1",
        courier_id="courier-1",
        status=WWOrderStatus.DONE,
        created_at=start,
        updated_at=start + timedelta(minutes=45),
        total_amount=Decimal("120.00"),
    )
    _seed_order(
        order_repo,
        order_id="order-2",
        courier_id="courier-2",
        status=WWOrderStatus.IN_TRANSIT,
        created_at=start + timedelta(hours=1),
        updated_at=start + timedelta(hours=1, minutes=15),
        total_amount=Decimal("80.50"),
    )

    json_response = await api_client.get("/api/v1/ww/report/deliveries")
    assert json_response.status_code == 200
    body = json_response.json()
    assert body["totals"]["total_orders"] == 2
    assert body["totals"]["total_amount"] == "200.50"
    assert body["totals"]["total_duration_min"] == pytest.approx(60.0)

    item_ids = {item["order_id"] for item in body["items"]}
    assert item_ids == {"order-1", "order-2"}
    order_1 = next(item for item in body["items"] if item["order_id"] == "order-1")
    assert order_1["courier_name"] == "Courier One"
    assert order_1["duration_min"] == pytest.approx(45.0)

    csv_response = await api_client.get(
        "/api/v1/ww/report/deliveries",
        params={"format": "csv"},
    )
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert csv_response.headers["content-disposition"].endswith("deliveries.csv")
    csv_body = csv_response.text
    assert csv_body.startswith("\ufeff")
    lines = [line for line in csv_body.splitlines() if line]
    assert lines[0].split(",")[0].lstrip("\ufeff") == "order_id"
    assert any(line.startswith("order-1") for line in lines[1:-1])
    assert lines[-1].startswith("TOTALS")
    assert lines[-1].split(",")[6] == "200.50"
    assert lines[-1].split(",")[-1] == "60.00"


@pytest.mark.asyncio
async def test_kmp4_export_payload(
    api_client: httpx.AsyncClient,
    ww_repositories: tuple[WalkingWarehouseCourierRepository, WalkingWarehouseOrderRepository],
) -> None:
    courier_repo, order_repo = ww_repositories
    courier_repo.create(
        courier_id="courier-77",
        display_name="Courier Seventy Seven",
        phone="+79000000077",
        is_active=True,
    )

    base = datetime(2024, 2, 1, 10, 0, tzinfo=datetime.UTC)
    _seed_order(
        order_repo,
        order_id="order-kmp4",
        courier_id="courier-77",
        status=WWOrderStatus.NEW,
        created_at=base,
        updated_at=base + timedelta(minutes=5),
        total_amount=Decimal("150.00"),
    )

    response = await api_client.get(
        "/api/v1/ww/export/kmp4",
        params={"status": WWOrderStatus.NEW.value},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    order = payload["items"][0]
    assert order["order_id"] == "order-kmp4"
    assert order["status_code"] == "new"
    assert order["total_amount"] == "150.00"
    assert order["courier_id"] == "courier-77"
    assert order["items"][0]["price"] == "150.00"

