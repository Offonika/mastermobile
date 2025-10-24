"""In-memory repositories modelling Walking Warehouse storages."""
from __future__ import annotations

from builtins import list as list_type
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal


class InvalidAssignmentStatusTransitionError(RuntimeError):
    """Raised when an assignment status transition is not allowed."""

    def __init__(self, current: str, new: str) -> None:
        self.current = current
        self.new = new
        super().__init__(f"Cannot transition assignment status from {current} to {new}.")


def _utcnow() -> datetime:
    """Return timezone-aware UTC timestamps."""

    return datetime.now(UTC)


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
    logs: list[OrderLogRecord] = field(default_factory=list)


@dataclass(slots=True)
class OrderLogRecord:
    """Audit record capturing status updates for an order."""

    status: str
    lat: float | None
    lon: float | None
    note: str | None
    created_at: datetime


class CourierAlreadyExistsError(RuntimeError):
    """Raised when attempting to create a courier with a duplicate identifier."""


class CourierNotFoundError(RuntimeError):
    """Raised when a courier identifier cannot be resolved."""


class OrderAlreadyExistsError(RuntimeError):
    """Raised when attempting to create an order that already exists."""


class OrderNotFoundError(RuntimeError):
    """Raised when an order identifier cannot be found."""


@dataclass(slots=True)
class AssignmentRecord:
    """Stored representation of an order assignment for a courier."""

    id: str
    order_id: str
    courier_id: str
    status: str
    created_at: datetime
    updated_at: datetime


class AssignmentAlreadyExistsError(RuntimeError):
    """Raised when attempting to create an assignment with an existing id."""


class AssignmentNotFoundError(RuntimeError):
    """Raised when an assignment identifier cannot be found."""


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

    def list(self, *, q: str | None = None) -> list_type[CourierRecord]:
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
            logs=[],
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
        courier_id: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list_type[OrderRecord]:
        records = list(self._orders.values())

        if statuses:
            allowed = {status.lower() for status in statuses}
            records = [record for record in records if record.status.lower() in allowed]

        if courier_id is not None:
            records = [record for record in records if record.courier_id == courier_id]

        if created_from is not None:
            records = [record for record in records if record.created_at >= created_from]

        if created_to is not None:
            records = [record for record in records if record.created_at <= created_to]

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

    def update_status(
        self,
        order_id: str,
        status: str,
        *,
        lat: float | None = None,
        lon: float | None = None,
        note: str | None = None,
    ) -> OrderRecord:
        record = self.get(order_id)
        timestamp = _utcnow()
        record.status = status
        record.updated_at = timestamp
        record.logs.append(
            OrderLogRecord(
                status=status,
                lat=lat,
                lon=lon,
                note=note,
                created_at=timestamp,
            )
        )
        return record

    def clear(self) -> None:
        self._orders.clear()

    def list_logs(self, order_id: str) -> list_type[OrderLogRecord]:
        record = self.get(order_id)
        return list(record.logs)


class WalkingWarehouseAssignmentRepository:
    """In-memory repository for courier order assignments."""

    _ALLOWED_TRANSITIONS = {
        "PENDING": {"ACCEPTED", "DECLINED"},
        "ACCEPTED": set(),
        "DECLINED": set(),
    }

    def __init__(self) -> None:
        self._assignments: dict[str, AssignmentRecord] = {}

    def create(
        self,
        *,
        assignment_id: str,
        order_id: str,
        courier_id: str,
        status: str = "PENDING",
    ) -> AssignmentRecord:
        if assignment_id in self._assignments:
            raise AssignmentAlreadyExistsError(assignment_id)

        timestamp = _utcnow()
        record = AssignmentRecord(
            id=assignment_id,
            order_id=order_id,
            courier_id=courier_id,
            status=status,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._assignments[assignment_id] = record
        return record

    def get(self, assignment_id: str) -> AssignmentRecord:
        record = self._assignments.get(assignment_id)
        if record is None:
            raise AssignmentNotFoundError(assignment_id)
        return record

    def _ensure_transition(self, record: AssignmentRecord, status: str) -> None:
        if record.status == status:
            return
        allowed = self._ALLOWED_TRANSITIONS.get(record.status, set())
        if status not in allowed:
            raise InvalidAssignmentStatusTransitionError(record.status, status)

    def accept(self, assignment_id: str) -> AssignmentRecord:
        record = self.get(assignment_id)
        self._ensure_transition(record, "ACCEPTED")
        if record.status != "ACCEPTED":
            record.status = "ACCEPTED"
            record.updated_at = _utcnow()
        return record

    def decline(self, assignment_id: str) -> AssignmentRecord:
        record = self.get(assignment_id)
        self._ensure_transition(record, "DECLINED")
        if record.status != "DECLINED":
            record.status = "DECLINED"
            record.updated_at = _utcnow()
        return record

    def reset_order(
        self,
        order_repository: WalkingWarehouseOrderRepository,
        order_id: str,
    ) -> OrderRecord:
        order_repository.assign_courier(order_id, None)
        return order_repository.update_status(order_id, "NEW")

    def clear(self) -> None:
        self._assignments.clear()
