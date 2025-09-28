from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.mw.src.db.models import (
    Base,
    DeliveryLog,
    DeliveryOrder,
    DeliveryOrderStatus,
)
from apps.mw.src.db.repositories.delivery_log import DeliveryLogRepository


@pytest.fixture()
def sqlite_engine() -> Engine:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[DeliveryOrder.__table__, DeliveryLog.__table__])
    yield engine
    engine.dispose()


def test_record_and_list_delivery_logs(sqlite_engine: Engine) -> None:
    session = Session(bind=sqlite_engine)
    try:
        order = DeliveryOrder(
            external_id="ORD-001",
            status=DeliveryOrderStatus.READY,
        )
        session.add(order)
        session.flush()

        repository = DeliveryLogRepository(session)
        first = repository.record(
            order_id=order.order_id,
            actor="user:alice",
            action="order_created",
            payload={"status": order.status.value},
        )
        second = repository.record(
            order_id=order.order_id,
            actor="system",
            action="status_changed",
            payload={"status": DeliveryOrderStatus.DELIVERED.value},
        )

        logs = repository.list_for_order(order.order_id)
        assert [entry.log_id for entry in logs] == [first.log_id, second.log_id]
        assert logs[0].payload_json == {"status": DeliveryOrderStatus.READY.value}
        assert logs[1].action == "status_changed"
    finally:
        session.close()


def test_list_for_missing_order_returns_empty(sqlite_engine: Engine) -> None:
    session = Session(bind=sqlite_engine)
    try:
        repository = DeliveryLogRepository(session)
        assert repository.list_for_order(uuid4()) == []
    finally:
        session.close()
