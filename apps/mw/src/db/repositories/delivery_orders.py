"""Repository helpers for delivery orders and assignments."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.mw.src.db.models import DeliveryOrder, DeliveryOrderStatus


class DeliveryOrderRepository:
    """CRUD facade around :class:`DeliveryOrder`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        external_id: str | None,
        status: DeliveryOrderStatus = DeliveryOrderStatus.NEW,
        courier_id: UUID | None = None,
        delivery_price: Decimal | None = None,
        cod_amount: Decimal | None = None,
        currency_code: str = "RUB",
        expected_delivery_at: datetime | None = None,
        metadata: dict[str, object] | None = None,
    ) -> DeliveryOrder:
        order = DeliveryOrder(
            external_id=external_id,
            status=status,
            courier_id=courier_id,
            delivery_price=delivery_price or Decimal("0"),
            cod_amount=cod_amount or Decimal("0"),
            currency_code=currency_code,
            expected_delivery_at=expected_delivery_at,
            metadata_json=metadata,
        )
        self._session.add(order)
        self._session.flush()
        return order

    def get(self, order_id: UUID) -> DeliveryOrder | None:
        statement: Select[tuple[DeliveryOrder]] = select(DeliveryOrder).where(
            DeliveryOrder.order_id == order_id
        )
        return self._session.scalar(statement)

    def get_by_external_id(self, external_id: str) -> DeliveryOrder | None:
        statement: Select[tuple[DeliveryOrder]] = select(DeliveryOrder).where(
            DeliveryOrder.external_id == external_id
        )
        return self._session.scalar(statement)

    def list_active_for_courier(
        self, courier_id: UUID
    ) -> list[DeliveryOrder]:
        statement = (
            select(DeliveryOrder)
            .where(
                DeliveryOrder.courier_id == courier_id,
                DeliveryOrder.status.in_(
                    [
                        DeliveryOrderStatus.NEW,
                        DeliveryOrderStatus.PICKING,
                        DeliveryOrderStatus.READY,
                        DeliveryOrderStatus.PICKED_UP,
                        DeliveryOrderStatus.ON_ROUTE,
                    ]
                ),
            )
            .order_by(DeliveryOrder.created_at)
        )
        return list(self._session.scalars(statement).all())

    def update_status(
        self,
        order: DeliveryOrder,
        status: DeliveryOrderStatus,
        *,
        delivered_at: datetime | None = None,
    ) -> DeliveryOrder:
        order.status = status
        if delivered_at is not None:
            order.delivered_at = delivered_at
        self._session.flush()
        return order

    def assign_courier(
        self, order: DeliveryOrder, *, courier_id: UUID | None
    ) -> DeliveryOrder:
        order.courier_id = courier_id
        self._session.flush()
        return order

    def update_amounts(
        self,
        order: DeliveryOrder,
        *,
        delivery_price: Decimal | None = None,
        cod_amount: Decimal | None = None,
    ) -> DeliveryOrder:
        if delivery_price is not None:
            order.delivery_price = delivery_price
        if cod_amount is not None:
            order.cod_amount = cod_amount
        self._session.flush()
        return order

    def delete(self, order: DeliveryOrder) -> None:
        self._session.delete(order)
        self._session.flush()
