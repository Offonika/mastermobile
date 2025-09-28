"""Serialization helpers for exporting Walking Warehouse orders to KMP4."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from apps.mw.src.domain.ww_statuses import (
    UnknownWWStatusError,
    map_ww_status_to_kmp4,
)
from apps.mw.src.integrations.ww.repositories import OrderItemRecord, OrderRecord


class KMP4ExportError(RuntimeError):
    """Raised when an order cannot be serialized for the KMP4 payload."""


@dataclass(slots=True, frozen=True)
class KMP4OrderPayload:
    """Structured representation of a WW order expected by the KMP4 upload."""

    order_id: str
    title: str
    customer_name: str
    status_code: str
    total_amount: Decimal
    currency_code: str
    courier_id: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    items: tuple[dict[str, Any], ...]


def _serialize_item(item: OrderItemRecord) -> dict[str, Any]:
    """Convert an order item into a serializable dictionary."""

    return {
        "sku": item.sku,
        "name": item.name,
        "qty": item.qty,
        "price": str(item.price),
    }


def serialize_order(order: OrderRecord) -> KMP4OrderPayload:
    """Map an order record into the structure consumed by KMP4."""

    try:
        status_code = map_ww_status_to_kmp4(order.status)
    except UnknownWWStatusError as exc:  # pragma: no cover - handled in unit tests
        raise KMP4ExportError(str(exc)) from exc

    items = tuple(_serialize_item(item) for item in order.items)

    return KMP4OrderPayload(
        order_id=order.id,
        title=order.title,
        customer_name=order.customer_name,
        status_code=status_code,
        total_amount=order.total_amount,
        currency_code=order.currency_code,
        courier_id=order.courier_id,
        notes=order.notes,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=items,
    )


__all__ = ["KMP4ExportError", "KMP4OrderPayload", "serialize_order"]
