"""Pydantic schemas for Walking Warehouse endpoints."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class WWBaseModel(BaseModel):
    """Base schema with common configuration for WW endpoints."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, use_enum_values=True)


class WWOrderStatus(str, Enum):
    """Statuses available for Walking Warehouse instant orders."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    TIMEOUT_ESCALATED = "TIMEOUT_ESCALATED"


class CourierCreate(WWBaseModel):
    """Payload for creating a courier."""

    id: str = Field(description="Unique identifier of the courier.")
    display_name: str = Field(description="Human readable name of the courier.")
    phone: str | None = Field(
        default=None,
        description="Contact phone number for the courier.",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the courier is active and available for assignments.",
    )


class Courier(CourierCreate):
    """Courier representation returned by the API."""

    created_at: datetime = Field(description="Timestamp when the courier was registered.")
    updated_at: datetime = Field(description="Timestamp of the last courier update.")


class CouriersResponse(WWBaseModel):
    """Collection of couriers."""

    items: List[Courier] = Field(description="List of couriers matching the filters.")


class OrderItemBase(WWBaseModel):
    """Common fields for order items."""

    sku: str = Field(description="Stock keeping unit of the product.")
    name: str = Field(description="Human readable product name.")
    qty: int = Field(ge=0, description="Quantity to be delivered.")
    price: Decimal = Field(ge=0, description="Unit price in the order currency.")


class OrderItem(OrderItemBase):
    """Order line returned by the API."""


class OrderCreateItem(OrderItemBase):
    """Order line used in create and update payloads."""


class Order(WWBaseModel):
    """Representation of a Walking Warehouse instant order."""

    id: str = Field(description="Unique identifier of the order.")
    title: str = Field(description="Title of the order shown to the courier.")
    customer_name: str = Field(description="Customer name associated with the order.")
    status: WWOrderStatus = Field(description="Current status of the order workflow.")
    courier_id: str | None = Field(
        default=None,
        description="Identifier of the courier assigned to the order.",
    )
    currency_code: str = Field(
        description="ISO-4217 currency code of the order totals.",
        min_length=3,
        max_length=3,
    )
    total_amount: Decimal = Field(ge=0, description="Total amount including taxes and delivery.")
    notes: str | None = Field(
        default=None,
        description="Optional notes displayed to the courier.",
    )
    created_at: datetime = Field(description="Timestamp when the order was created.")
    updated_at: datetime = Field(description="Timestamp when the order was last updated.")
    items: List[OrderItem] = Field(
        description="Order lines for the courier to deliver.",
        min_length=1,
    )


class OrderCreate(WWBaseModel):
    """Payload for creating an instant order."""

    id: str | None = Field(
        default=None,
        description="Optional identifier; generated when omitted.",
    )
    title: str = Field(description="Title of the order shown to the courier.")
    customer_name: str = Field(description="Customer name associated with the order.")
    status: WWOrderStatus = Field(
        default=WWOrderStatus.DRAFT,
        description="Initial status of the order.",
    )
    courier_id: str | None = Field(
        default=None,
        description="Identifier of the courier assigned to the order.",
    )
    currency_code: str = Field(
        default="RUB",
        description="ISO-4217 currency code of the order totals.",
        min_length=3,
        max_length=3,
    )
    total_amount: Decimal = Field(
        ge=0,
        description="Total amount including taxes and delivery.",
    )
    notes: str | None = Field(
        default=None,
        description="Optional notes displayed to the courier.",
    )
    items: List[OrderCreateItem] = Field(
        description="Order lines for the courier to deliver.",
        min_length=1,
    )


class OrderUpdate(WWBaseModel):
    """Payload for updating an instant order."""

    title: str | None = Field(
        default=None,
        description="Updated title of the order.",
    )
    customer_name: str | None = Field(
        default=None,
        description="Updated customer name.",
    )
    notes: str | None = Field(
        default=None,
        description="Updated notes for the courier.",
    )
    currency_code: str | None = Field(
        default=None,
        description="Updated currency code.",
        min_length=3,
        max_length=3,
    )
    total_amount: Decimal | None = Field(
        default=None,
        ge=0,
        description="Updated order total.",
    )
    items: List[OrderCreateItem] | None = Field(
        default=None,
        description="Replacement set of order lines.",
    )


class OrderAssign(WWBaseModel):
    """Payload assigning a courier to an order."""

    courier_id: str | None = Field(
        default=None,
        description="Identifier of the courier or null to unassign.",
    )


class OrderStatusUpdate(WWBaseModel):
    """Payload for transitioning an order to a new status."""

    status: WWOrderStatus = Field(description="New status for the order.")


class OrderListResponse(WWBaseModel):
    """Collection of orders with metadata."""

    items: List[Order] = Field(description="Orders matching requested filters.")
    total: int = Field(ge=0, description="Total number of orders after filters.")
