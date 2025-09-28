"""Integration tests for delivery-related ORM mappings."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
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


def _create_all(engine) -> None:
    Base.metadata.create_all(
        engine,
        tables=[
            Courier.__table__,
            DeliveryOrder.__table__,
            DeliveryAssignment.__table__,
            DeliveryLog.__table__,
        ],
    )


def test_delivery_order_relationships_roundtrip() -> None:
    """Ensure courier/order/assignment/log relations work end-to-end."""

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_all(engine)

    courier_id = uuid4()

    with Session(engine) as session:
        courier = Courier(
            courier_id=courier_id,
            external_id="courier-ext-1",
            full_name="Иван Курьер",
            phone="+79991234567",
            status=CourierStatus.ACTIVE,
        )
        order = DeliveryOrder(
            courier=courier,
            external_id="ORD-1C-123",
            status=DeliveryOrderStatus.READY,
            delivery_price=Decimal("150.50"),
            cod_amount=Decimal("500.00"),
            currency_code="RUB",
            expected_delivery_at=datetime(2024, 4, 1, tzinfo=timezone.utc),
        )
        assignment = DeliveryAssignment(
            order=order,
            courier=courier,
            status=DeliveryAssignmentStatus.ACCEPTED,
        )
        log = DeliveryLog(
            order=order,
            assignment=assignment,
            courier=courier,
            status=DeliveryLogStatus.SUCCESS,
            event_type="status_changed",
            message="Order picked up",
            payload={"actor": "courier"},
        )

        session.add_all([courier, order, assignment, log])
        session.commit()
        order_id = order.order_id
        assignment_id = assignment.assignment_id
        session.expunge_all()

        loaded_order = session.scalars(
            select(DeliveryOrder).where(DeliveryOrder.order_id == order_id)
        ).one()

        assert loaded_order.courier is not None
        assert loaded_order.courier.full_name == "Иван Курьер"
        assert loaded_order.assignments[0].status is DeliveryAssignmentStatus.ACCEPTED
        assert loaded_order.logs[0].status is DeliveryLogStatus.SUCCESS
        assert loaded_order.logs[0].assignment.assignment_id == assignment_id
        assert loaded_order.logs[0].payload["actor"] == "courier"
        assert loaded_order.logs[0].payload["kmp4_exported"] is False

    engine.dispose()


def test_delivery_log_payload_normalization() -> None:
    """Delivery log payloads must always expose the KMP4 export flag."""

    default_payload = DeliveryLog.normalize_payload()
    assert default_payload == {"kmp4_exported": False}

    explicit_false = DeliveryLog.normalize_payload({"notes": "value"})
    assert explicit_false["kmp4_exported"] is False
    assert explicit_false["notes"] == "value"

    explicit_true = DeliveryLog.normalize_payload(
        {"kmp4_exported": "true", "notes": "value"}
    )
    assert explicit_true["kmp4_exported"] is True
    assert explicit_true["notes"] == "value"


def test_delivery_order_amounts_cannot_be_negative() -> None:
    """Ensure delivery orders respect non-negative amount checks."""

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    _create_all(engine)

    with Session(engine) as session:
        courier = Courier(
            full_name="Никита Курьер",
            phone="+79998887766",
        )
        order = DeliveryOrder(
            courier=courier,
            external_id="ORD-NEG",
            status=DeliveryOrderStatus.NEW,
            delivery_price=Decimal("-1.00"),
        )

        session.add(order)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()

    engine.dispose()
