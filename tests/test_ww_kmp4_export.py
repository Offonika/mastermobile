from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.mw.src.api.schemas.ww import WWOrderStatus
from apps.mw.src.domain.ww_statuses import (
    WW_TO_KMP4_STATUS,
    UnknownWWStatusError,
    map_ww_status_to_kmp4,
)
from apps.mw.src.integrations.ww.kmp4_export import (
    KMP4ExportError,
    KMP4OrderPayload,
    serialize_order,
)
from apps.mw.src.integrations.ww.repositories import OrderItemRecord, OrderRecord


def _order_record(status: str) -> OrderRecord:
    timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    return OrderRecord(
        id="order-1",
        title="Sample order",
        customer_name="Alice",
        status=status,
        courier_id="courier-1",
        currency_code="RUB",
        total_amount=Decimal("100.50"),
        notes="Deliver before 18:00",
        created_at=timestamp,
        updated_at=timestamp,
        items=[
            OrderItemRecord(sku="SKU-1", name="Coffee", qty=1, price=Decimal("100.50"))
        ],
    )


def test_mapping_covers_every_status() -> None:
    mapped_statuses = set(WW_TO_KMP4_STATUS.keys())
    assert mapped_statuses == set(WWOrderStatus)

    for status in WWOrderStatus:
        assert map_ww_status_to_kmp4(status) == WW_TO_KMP4_STATUS[status]
        assert map_ww_status_to_kmp4(status.value) == WW_TO_KMP4_STATUS[status]


def test_mapping_rejects_unknown_status() -> None:
    with pytest.raises(UnknownWWStatusError):
        map_ww_status_to_kmp4("UNKNOWN")


def test_serialize_order_uses_mapping() -> None:
    order = _order_record(WWOrderStatus.NEW.value)
    payload = serialize_order(order)
    assert isinstance(payload, KMP4OrderPayload)
    assert payload.status_code == WW_TO_KMP4_STATUS[WWOrderStatus.NEW]


def test_serialize_order_raises_for_unmapped_status() -> None:
    order = _order_record("UNMAPPED")
    with pytest.raises(KMP4ExportError) as excinfo:
        serialize_order(order)
    assert "UNMAPPED" in str(excinfo.value)
