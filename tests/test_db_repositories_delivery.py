"""Unit tests for delivery repositories."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.mw.src.db.models import (
    Base,
    Courier,
    CourierStatus,
    DeliveryAssignment,
    DeliveryAssignmentStatus,
    DeliveryLog,
    DeliveryLogStatus,
    DeliveryOrder,
    DeliveryOrderStatus,
)
from apps.mw.src.db.repositories.couriers import CourierRepository
from apps.mw.src.db.repositories.delivery_assignments import (
    DeliveryAssignmentRepository,
)
from apps.mw.src.db.repositories.delivery_logs import DeliveryLogRepository
from apps.mw.src.db.repositories.delivery_orders import DeliveryOrderRepository


@pytest.fixture()
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Courier.__table__,
            DeliveryOrder.__table__,
            DeliveryAssignment.__table__,
            DeliveryLog.__table__,
        ],
    )
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_courier_repository_crud(session: Session) -> None:
    repo = CourierRepository(session)
    courier = repo.create(
        external_id="C-001",
        full_name="Курьер Тестовый",
        phone="+79990000000",
        email="courier@example.com",
        status=CourierStatus.ONBOARDING,
        metadata={"region": "msk"},
    )

    assert courier.courier_id is not None
    assert repo.get(courier.courier_id) is courier

    repo.update_status(courier, CourierStatus.ACTIVE)
    repo.update_contacts(courier, phone="+79991112233", metadata={"region": "spb"})

    listed = repo.list_by_status(CourierStatus.ACTIVE)
    assert listed == [courier]
    assert courier.phone.endswith("2233")
    assert courier.metadata_json == {"region": "spb"}

    repo.delete(courier)
    assert repo.get(courier.courier_id) is None


def test_delivery_order_repository_flow(session: Session) -> None:
    courier_repo = CourierRepository(session)
    order_repo = DeliveryOrderRepository(session)

    courier = courier_repo.create(
        external_id="C-002",
        full_name="Семен Курьер",
        phone="+79993334455",
        status=CourierStatus.ACTIVE,
    )

    order = order_repo.create(
        external_id="ORD-001",
        courier_id=courier.courier_id,
        delivery_price=Decimal("250.00"),
        cod_amount=Decimal("500.00"),
        expected_delivery_at=datetime(2024, 4, 2, 12, 0, tzinfo=UTC),
        metadata={"priority": "high"},
    )

    assert order_repo.get(order.order_id) is order
    assert order_repo.get_by_external_id("ORD-001") is order

    active_orders = order_repo.list_active_for_courier(courier.courier_id)
    assert active_orders == [order]

    order_repo.update_status(order, DeliveryOrderStatus.DELIVERED, delivered_at=datetime.now(tz=UTC))
    order_repo.assign_courier(order, courier_id=None)
    order_repo.update_amounts(order, delivery_price=Decimal("260.00"))

    assert order.status is DeliveryOrderStatus.DELIVERED
    assert order.courier_id is None
    assert order.delivery_price == Decimal("260.00")

    order_repo.delete(order)
    assert order_repo.get(order.order_id) is None


def test_delivery_assignment_repository_flow(session: Session) -> None:
    courier_repo = CourierRepository(session)
    order_repo = DeliveryOrderRepository(session)
    assignment_repo = DeliveryAssignmentRepository(session)

    courier = courier_repo.create(
        external_id="C-003",
        full_name="Мария Курьер",
        phone="+79995556677",
        status=CourierStatus.ACTIVE,
    )
    order = order_repo.create(
        external_id="ORD-ASSIGN",
        courier_id=courier.courier_id,
        status=DeliveryOrderStatus.READY,
    )

    assignment = assignment_repo.create(
        order_id=order.order_id,
        courier_id=courier.courier_id,
        notes="Назначено автоматически",
    )

    assert assignment_repo.get(assignment.assignment_id) is assignment

    active_assignments = assignment_repo.list_active_for_order(order.order_id)
    assert active_assignments == [assignment]

    assignment_repo.update_status(
        assignment,
        DeliveryAssignmentStatus.IN_PROGRESS,
        accepted_at=datetime(2024, 4, 1, 9, 0, tzinfo=UTC),
    )
    assignment_repo.reassign(
        assignment,
        courier_id=courier.courier_id,
        notes="Подтверждение",
    )
    assignment_repo.update_status(
        assignment,
        DeliveryAssignmentStatus.COMPLETED,
        completed_at=datetime(2024, 4, 1, 10, 0, tzinfo=UTC),
    )

    assert assignment.status is DeliveryAssignmentStatus.COMPLETED
    assert assignment.completed_at is not None

    assignment_repo.delete(assignment)
    assert assignment_repo.get(assignment.assignment_id) is None


def test_delivery_log_repository_records_events(session: Session) -> None:
    courier_repo = CourierRepository(session)
    order_repo = DeliveryOrderRepository(session)
    log_repo = DeliveryLogRepository(session)

    courier = courier_repo.create(
        external_id="C-004",
        full_name="Антон Курьер",
        phone="+79990009999",
        status=CourierStatus.ACTIVE,
    )
    order = order_repo.create(
        external_id="ORD-LOG",
        courier_id=courier.courier_id,
        status=DeliveryOrderStatus.ON_ROUTE,
    )

    log_entry = log_repo.create(
        order_id=order.order_id,
        status=DeliveryLogStatus.INFO,
        event_type="status_change",
        courier_id=courier.courier_id,
        message="Заказ в пути",
        payload={"location": "55.75,37.61"},
    )

    flagged_entry = log_repo.create(
        order_id=order.order_id,
        status=DeliveryLogStatus.SUCCESS,
        event_type="kmp4_export",
        courier_id=courier.courier_id,
        message="Отчёт выгружен",
        payload={"actor": "scheduler"},
        kmp4_exported=True,
    )

    assert log_entry.id is not None
    assert flagged_entry.payload["kmp4_exported"] is True

    logs = log_repo.list_for_order(order.order_id)
    assert logs == [log_entry, flagged_entry]
    assert logs[0].payload["location"] == "55.75,37.61"
    assert logs[0].payload["kmp4_exported"] is False

    log_repo.delete(flagged_entry)
    log_repo.delete(log_entry)
    assert log_repo.list_for_order(order.order_id) == []
