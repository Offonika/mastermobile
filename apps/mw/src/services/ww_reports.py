"""Helpers generating Walking Warehouse analytical reports."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from apps.mw.src.integrations.ww import (
    CourierNotFoundError,
    OrderRecord,
    WalkingWarehouseCourierRepository,
    WalkingWarehouseOrderRepository,
)
from apps.mw.src.integrations.ww.kmp4_export import KMP4OrderPayload, serialize_order


@dataclass(slots=True)
class DeliveryReportRow:
    """Aggregated representation of a single Walking Warehouse delivery."""

    order_id: str
    courier_id: str | None
    courier_name: str | None
    status: str
    title: str
    customer_name: str
    total_amount: Decimal
    currency_code: str
    created_at: datetime
    updated_at: datetime
    duration_min: float


@dataclass(slots=True)
class DeliveryReport:
    """Collection of deliveries with accompanying totals."""

    rows: list[DeliveryReportRow]
    total_amount: Decimal
    total_duration_min: float

    @property
    def total_orders(self) -> int:
        return len(self.rows)


class WWReportService:
    """Domain service producing Walking Warehouse analytical exports."""

    def __init__(
        self,
        order_repository: WalkingWarehouseOrderRepository,
        courier_repository: WalkingWarehouseCourierRepository,
    ) -> None:
        self._order_repository = order_repository
        self._courier_repository = courier_repository

    def _resolve_courier_name(self, courier_id: str | None) -> str | None:
        if courier_id is None:
            return None
        try:
            courier = self._courier_repository.get(courier_id)
        except CourierNotFoundError:
            return None
        return courier.display_name

    @staticmethod
    def _duration_minutes(order: OrderRecord) -> float:
        delta = order.updated_at - order.created_at
        return max(delta.total_seconds() / 60.0, 0.0)

    def generate_delivery_report(
        self,
        *,
        statuses: Iterable[str] | None = None,
        courier_id: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> DeliveryReport:
        orders = self._order_repository.list(
            statuses=statuses,
            courier_id=courier_id,
            created_from=created_from,
            created_to=created_to,
        )

        rows: list[DeliveryReportRow] = []
        total_amount = Decimal("0")
        total_duration = 0.0
        for order in orders:
            courier_name = self._resolve_courier_name(order.courier_id)
            duration_min = self._duration_minutes(order)
            rows.append(
                DeliveryReportRow(
                    order_id=order.id,
                    courier_id=order.courier_id,
                    courier_name=courier_name,
                    status=order.status,
                    title=order.title,
                    customer_name=order.customer_name,
                    total_amount=order.total_amount,
                    currency_code=order.currency_code,
                    created_at=order.created_at,
                    updated_at=order.updated_at,
                    duration_min=duration_min,
                )
            )
            total_amount += order.total_amount
            total_duration += duration_min

        return DeliveryReport(
            rows=rows,
            total_amount=total_amount,
            total_duration_min=total_duration,
        )

    def build_kmp4_export(
        self,
        *,
        statuses: Iterable[str] | None = None,
        courier_id: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[KMP4OrderPayload]:
        orders = self._order_repository.list(
            statuses=statuses,
            courier_id=courier_id,
            created_from=created_from,
            created_to=created_to,
        )

        payloads = [serialize_order(order) for order in orders]
        return payloads


__all__ = ["DeliveryReport", "DeliveryReportRow", "WWReportService"]
