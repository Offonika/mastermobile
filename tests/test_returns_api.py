"""Integration tests for the returns API endpoints."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import pytest_asyncio
from apps.mw.src.api.dependencies import reset_idempotency_cache
from apps.mw.src.app import app
from apps.mw.src.db.models import Base, Return, ReturnLine
from apps.mw.src.db.session import configure_engine, get_session
from apps.mw.src.db.session import engine as default_engine

BASE_URL = "http://testserver"


@pytest.fixture(autouse=True)
def _clear_idempotency_cache() -> None:
    reset_idempotency_cache()
    yield
    reset_idempotency_cache()


@pytest.fixture()
def sqlite_engine() -> Engine:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[Return.__table__, ReturnLine.__table__])
    configure_engine(engine)
    yield engine
    configure_engine(default_engine)
    engine.dispose()


@pytest_asyncio.fixture()
async def api_client(sqlite_engine: Engine) -> httpx.AsyncClient:
    def override_get_session() -> Session:
        session = Session(bind=sqlite_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


def _sample_payload() -> dict[str, object]:
    return {
        "source": "warehouse",
        "courier_id": "courier-001",
        "order_id_1c": "000123",
        "comment": "Initial pickup",
        "items": [
            {
                "sku": "SKU-1001",
                "qty": 1,
                "quality": "new",
                "reason_code": "customer_changed_mind",
            }
        ],
    }


@pytest.mark.asyncio
async def test_create_and_retrieve_return(api_client: httpx.AsyncClient) -> None:
    payload = _sample_payload()
    headers = {"Idempotency-Key": "key-create-1", "X-Request-Id": "req-create-1"}

    create_response = await api_client.post("/api/v1/returns", json=payload, headers=headers)
    assert create_response.status_code == 201
    body = create_response.json()
    return_id = body["id"]
    assert create_response.headers["Location"].endswith(return_id)
    assert create_response.headers["Idempotency-Key"] == headers["Idempotency-Key"]
    assert body["items"]

    list_response = await api_client.get("/api/v1/returns", headers={"X-Request-Id": "req-list-1"})
    assert list_response.status_code == 200
    assert any(item["id"] == return_id for item in list_response.json()["items"])

    get_response = await api_client.get(
        f"/api/v1/returns/{return_id}", headers={"X-Request-Id": "req-get-1"}
    )
    assert get_response.status_code == 200
    assert get_response.json()["id"] == return_id


@pytest.mark.asyncio
async def test_idempotency_conflict_on_different_payload(api_client: httpx.AsyncClient) -> None:
    payload = _sample_payload()
    headers = {"Idempotency-Key": "key-conflict", "X-Request-Id": "req-conflict-1"}

    first_response = await api_client.post("/api/v1/returns", json=payload, headers=headers)
    assert first_response.status_code == 201

    modified_payload = dict(payload)
    modified_payload["comment"] = "Changed"

    conflict_response = await api_client.post(
        "/api/v1/returns",
        json=modified_payload,
        headers={"Idempotency-Key": "key-conflict", "X-Request-Id": "req-conflict-2"},
    )
    assert conflict_response.status_code == 409
    problem = conflict_response.json()
    assert problem["title"] == "Idempotency conflict"
    assert problem["status"] == 409


@pytest.mark.asyncio
async def test_idempotent_replay_returns_cached_response(
    api_client: httpx.AsyncClient, sqlite_engine: Engine
) -> None:
    payload = _sample_payload()
    headers = {"Idempotency-Key": "key-replay-1", "X-Request-Id": "req-replay-1"}

    first_response = await api_client.post("/api/v1/returns", json=payload, headers=headers)
    assert first_response.status_code == 201
    first_body = first_response.json()
    first_location = first_response.headers["Location"]

    replay_headers = {"Idempotency-Key": "key-replay-1", "X-Request-Id": "req-replay-2"}
    replay_response = await api_client.post("/api/v1/returns", json=payload, headers=replay_headers)

    assert replay_response.status_code == 200
    assert replay_response.json() == first_body
    assert replay_response.headers["Location"] == first_location
    assert replay_response.headers["Idempotency-Key"] == headers["Idempotency-Key"]

    with Session(bind=sqlite_engine) as session:
        total_returns = session.scalar(select(func.count(Return.return_id)))
        assert total_returns == 1


@pytest.mark.asyncio
async def test_update_return_replaces_items(api_client: httpx.AsyncClient) -> None:
    headers = {"Idempotency-Key": "key-update-1", "X-Request-Id": "req-update-1"}
    create_response = await api_client.post("/api/v1/returns", json=_sample_payload(), headers=headers)
    return_id = create_response.json()["id"]

    update_payload = {
        "source": "warehouse",
        "courier_id": "courier-002",
        "order_id_1c": "000124",
        "comment": "Updated items",
        "items": [
            {
                "sku": "SKU-2002",
                "qty": 2,
                "quality": "defect",
                "reason_code": "damaged_package",
                "reason_note": "Box was crushed",
            }
        ],
    }
    update_headers = {"Idempotency-Key": "key-update-2", "X-Request-Id": "req-update-2"}
    update_response = await api_client.put(
        f"/api/v1/returns/{return_id}", json=update_payload, headers=update_headers
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["courier_id"] == "courier-002"
    assert updated["items"][0]["sku"] == "SKU-2002"
    assert updated["items"][0]["qty"] == 2


@pytest.mark.asyncio
async def test_delete_return_removes_resource(api_client: httpx.AsyncClient) -> None:
    headers = {"Idempotency-Key": "key-delete-1", "X-Request-Id": "req-delete-1"}
    create_response = await api_client.post("/api/v1/returns", json=_sample_payload(), headers=headers)
    return_id = create_response.json()["id"]

    delete_headers = {"Idempotency-Key": "key-delete-2", "X-Request-Id": "req-delete-2"}
    delete_response = await api_client.delete(
        f"/api/v1/returns/{return_id}", headers=delete_headers
    )
    assert delete_response.status_code == 204

    missing_response = await api_client.get(
        f"/api/v1/returns/{return_id}", headers={"X-Request-Id": "req-delete-3"}
    )
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_missing_idempotency_key_triggers_validation_error(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post("/api/v1/returns", json=_sample_payload())
    assert response.status_code == 422
    payload = response.json()
    assert payload["title"] == "Invalid Idempotency-Key header"
    assert payload["status"] == 422


@pytest.mark.asyncio
async def test_get_unknown_return_returns_not_found(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        f"/api/v1/returns/{uuid4()}", headers={"X-Request-Id": "req-missing-1"}
    )
    assert response.status_code == 404
    payload = response.json()
    assert payload["title"] == "Return not found"
