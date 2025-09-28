import httpx
import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.mw.src.app import app
from apps.mw.src.db.models import Base, DeliveryLog, DeliveryOrder
from apps.mw.src.db.session import configure_engine, engine as default_engine, get_session

BASE_URL = "http://testserver"


@pytest.fixture()
def sqlite_engine() -> Engine:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[DeliveryOrder.__table__, DeliveryLog.__table__])
    configure_engine(engine)
    yield engine
    configure_engine(default_engine)
    engine.dispose()


@pytest_asyncio.fixture()
async def api_client(sqlite_engine: Engine) -> httpx.AsyncClient:
    def override_session() -> Session:
        session = Session(bind=sqlite_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


def _create_payload() -> dict[str, object]:
    return {
        "external_id": "WW-001",
        "status": "ready",
        "courier_id": None,
        "payload": {"items": 2, "amount": 1990},
        "actor": "user:manager-1",
    }


@pytest.mark.asyncio
async def test_delivery_log_entries_created_for_order_lifecycle(api_client: httpx.AsyncClient) -> None:
    create_response = await api_client.post("/api/v1/ww/orders", json=_create_payload())
    assert create_response.status_code == 201
    order = create_response.json()
    order_id = order["id"]

    logs_response = await api_client.get(f"/api/v1/ww/orders/{order_id}/logs")
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert [entry["action"] for entry in logs] == ["order_created"]
    assert logs[0]["actor"] == "user:manager-1"

    update_payload = {
        "courier_id": "courier-7",
        "payload": {"items": 3, "note": "Updated order"},
        "actor": "user:planner",
    }
    update_response = await api_client.put(f"/api/v1/ww/orders/{order_id}", json=update_payload)
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["courier_id"] == "courier-7"

    assign_payload = {"courier_id": "courier-42", "actor": "system"}
    assign_response = await api_client.post(
        f"/api/v1/ww/orders/{order_id}/assign", json=assign_payload
    )
    assert assign_response.status_code == 200
    assigned = assign_response.json()
    assert assigned["courier_id"] == "courier-42"

    status_payload = {"status": "delivered", "actor": "courier:42", "reason": "delivered"}
    status_response = await api_client.post(
        f"/api/v1/ww/orders/{order_id}/status", json=status_payload
    )
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["status"] == "delivered"

    final_logs_response = await api_client.get(f"/api/v1/ww/orders/{order_id}/logs")
    assert final_logs_response.status_code == 200
    final_logs = final_logs_response.json()
    assert [entry["action"] for entry in final_logs] == [
        "order_created",
        "order_updated",
        "order_assigned",
        "status_changed",
    ]
    assert final_logs[-1]["payload"]["status"] == "delivered"
