"""Schemas for Walking Warehouse analytical endpoints."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class WWReportBaseModel(BaseModel):
    """Base model configuration for report schemas."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DeliveryReportRow(WWReportBaseModel):
    """Single row in the delivery report response."""

    order_id: str = Field(description="Identifier of the Walking Warehouse order.")
    courier_id: str | None = Field(
        default=None,
        description="Identifier of the courier assigned to the order.",
    )
    courier_name: str | None = Field(
        default=None,
        description="Display name of the courier assigned to the order.",
    )
    status: str = Field(description="Current order status in Walking Warehouse.")
    title: str = Field(description="Title of the delivery visible to the courier.")
    customer_name: str = Field(description="Customer associated with the delivery.")
    total_amount: Decimal = Field(
        ge=0,
        description="Total amount of the order in its currency.",
    )
    currency_code: str = Field(
        description="ISO-4217 currency code of the order amount.",
        min_length=3,
        max_length=3,
    )
    created_at: datetime = Field(
        description="Timestamp when the order was created in Walking Warehouse.",
    )
    updated_at: datetime = Field(
        description="Timestamp when the order last changed status.",
    )
    duration_min: float = Field(
        ge=0,
        description="Elapsed minutes between creation and last update.",
    )


class DeliveryReportTotals(WWReportBaseModel):
    """Aggregated totals for the delivery report."""

    total_orders: int = Field(ge=0, description="Number of deliveries in the report.")
    total_amount: Decimal = Field(
        ge=0,
        description="Sum of order totals across all deliveries.",
    )
    total_duration_min: float = Field(
        ge=0,
        description="Sum of delivery durations in minutes across the report.",
    )


class DeliveryReportResponse(WWReportBaseModel):
    """Response payload returned by the delivery report endpoint."""

    items: list[DeliveryReportRow] = Field(
        description="Delivery records matching the requested filters.",
    )
    totals: DeliveryReportTotals = Field(
        description="Aggregated totals for convenience in UI/export consumers.",
    )


class KMP4OrderItem(WWReportBaseModel):
    """Order line included in the KMP4 export payload."""

    sku: str = Field(description="Stock keeping unit used in Walking Warehouse.")
    name: str = Field(description="Item name displayed to the courier.")
    qty: int = Field(ge=0, description="Quantity of the item to deliver.")
    price: str = Field(description="Unit price encoded as a decimal string.")


class KMP4Order(WWReportBaseModel):
    """Order payload compatible with the KMP4 upload extension."""

    order_id: str = Field(description="Identifier of the order exported to KMP4.")
    title: str = Field(description="Order title as displayed in the UI.")
    customer_name: str = Field(description="Customer associated with the order.")
    status_code: str = Field(description="Status code mapped to the KMP4 domain.")
    total_amount: Decimal = Field(
        ge=0,
        description="Total amount of the order in its currency.",
    )
    currency_code: str = Field(
        description="ISO-4217 currency code of the order amount.",
        min_length=3,
        max_length=3,
    )
    courier_id: str | None = Field(
        default=None,
        description="Identifier of the courier assigned to the order.",
    )
    notes: str | None = Field(
        default=None,
        description="Optional notes for the courier exported to KMP4.",
    )
    created_at: datetime = Field(
        description="Timestamp when the order was created in Walking Warehouse.",
    )
    updated_at: datetime = Field(
        description="Timestamp of the latest order change exported to KMP4.",
    )
    items: list[KMP4OrderItem] = Field(
        description="Order lines included in the export payload.",
    )


class KMP4ExportResponse(WWReportBaseModel):
    """Response containing orders serialized for KMP4."""

    items: list[KMP4Order] = Field(
        description="Orders ready to be consumed by the KMP4 extension.",
    )
    total: int = Field(ge=0, description="Number of orders in the export payload.")


__all__ = [
    "DeliveryReportResponse",
    "DeliveryReportRow",
    "DeliveryReportTotals",
    "KMP4ExportResponse",
    "KMP4Order",
    "KMP4OrderItem",
]
