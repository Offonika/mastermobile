"""In-memory repositories modelling Walking Warehouse storages."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Sequence


def _utcnow() -> datetime:
    """Return timezone-aware UTC timestamps."""

    return datetime.now(timezone.utc)


@dataclass(slots=True)
class CourierRecord:
    """Stored representation of a courier in Walking Warehouse."""

    id: str
    display_name: str
    phone: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class OrderItemRecord:
    """Line item for a Walking Warehouse order."""

    sku: str
    name: str
    qty: int
    price: Decimal


@dataclass(slots=True)
class OrderRecord:
    """Stored representation of an instant order from Walking Warehouse."""

    id: str
    title: str
    customer_name: str
    status: str
    courier_id: str | None
    currency_code: str
    total_amount: Decimal
    notes: str | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRecord] = field(default_factory=list)


class CourierAlreadyExistsError(RuntimeError):
    """Raised when attempting to create a courier with a duplicate identifier."""


class CourierNotFoundError(RuntimeError):
    """Raised when a courier identifier cannot be resolved."""


class OrderAlreadyExistsError(RuntimeError):
    """Raised when attempting to create an order that already exists."""


class OrderNotFoundError(RuntimeError):
    """Raised when an order identifier cannot be found."""


class WalkingWarehouseCourierRepository:
    """Simple repository handling courier entities."""

    def __init__(self) -> None:
        self._couriers: dict[str, CourierRecord] = {}

    def create(
        self,
        *,
        courier_id: str,
        display_name: str,
        phone: str | None,
        is_active: bool,
    ) -> CourierRecord:
        if courier_id in self._couriers:
            raise CourierAlreadyExistsError(courier_id)

        timestamp = _utcnow()
        record = CourierRecord(
            id=courier_id,
            display_name=display_name,
            phone=phone,
            is_active=is_active,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._couriers[courier_id] = record
        return record

    def get(self, courier_id: str) -> CourierRecord:
        record = self._couriers.get(courier_id)
        if record is None:
            raise CourierNotFoundError(courier_id)
        return record

    def list(self, *, q: str | None = None) -> list[CourierRecord]:
        records = list(self._couriers.values())
        if q:
            needle = q.strip().lower()
            if needle:
                records = [
                    courier
                    for courier in records
                    if needle in courier.display_name.lower()
                    or needle in courier.id.lower()
                    or (courier.phone or "").lower().find(needle) != -1
                ]
        records.sort(key=lambda courier: (courier.display_name.lower(), courier.id))
        return records

    def clear(self) -> None:
        self._couriers.clear()


class WalkingWarehouseOrderRepository:
    """Simple repository handling order entities."""

    def __init__(self) -> None:
        self._orders: dict[str, OrderRecord] = {}

    def create(
        self,
        *,
        order_id: str,
        title: str,
        customer_name: str,
        status: str,
        courier_id: str | None,
        currency_code: str,
        total_amount: Decimal,
        notes: str | None,
        items: Sequence[OrderItemRecord],
    ) -> OrderRecord:
        if order_id in self._orders:
            raise OrderAlreadyExistsError(order_id)

        timestamp = _utcnow()
        record = OrderRecord(
            id=order_id,
            title=title,
            customer_name=customer_name,
            status=status,
            courier_id=courier_id,
            currency_code=currency_code,
            total_amount=total_amount,
            notes=notes,
            created_at=timestamp,
            updated_at=timestamp,
            items=list(items),
        )
        self._orders[order_id] = record
        return record

    def get(self, order_id: str) -> OrderRecord:
        record = self._orders.get(order_id)
        if record is None:
            raise OrderNotFoundError(order_id)
        return record

    def list(
        self,
        *,
        statuses: Iterable[str] | None = None,
        q: str | None = None,
    ) -> list[OrderRecord]:
        records = list(self._orders.values())

        if statuses:
            allowed = {status.lower() for status in statuses}
            records = [record for record in records if record.status.lower() in allowed]

        if q:
            needle = q.strip().lower()
            if needle:
                records = [
                    record
                    for record in records
                    if needle in record.id.lower()
                    or needle in record.title.lower()
                    or needle in record.customer_name.lower()
                ]

        records.sort(key=lambda record: (record.created_at, record.id), reverse=True)
        return records

    def update(
        self,
        order_id: str,
        *,
        title: str | None = None,
        customer_name: str | None = None,
        notes: str | None = None,
        items: Sequence[OrderItemRecord] | None = None,
        total_amount: Decimal | None = None,
        currency_code: str | None = None,
    ) -> OrderRecord:
        record = self.get(order_id)

        updated = False
        if title is not None:
            record.title = title
            updated = True
        if customer_name is not None:
            record.customer_name = customer_name
            updated = True
        if notes is not None:
            record.notes = notes
            updated = True
        if items is not None:
            record.items = list(items)
            updated = True
        if total_amount is not None:
            record.total_amount = total_amount
            updated = True
        if currency_code is not None:
            record.currency_code = currency_code
            updated = True

        if updated:
            record.updated_at = _utcnow()
        return record

    def assign_courier(self, order_id: str, courier_id: str | None) -> OrderRecord:
        record = self.get(order_id)
        record.courier_id = courier_id
        record.updated_at = _utcnow()
        return record

    def update_status(self, order_id: str, status: str) -> OrderRecord:
        record = self.get(order_id)
        record.status = status
        record.updated_at = _utcnow()
        return record

    def clear(self) -> None:
        self._orders.clear()
