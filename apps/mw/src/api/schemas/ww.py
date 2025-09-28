"""Pydantic schemas for Walking Warehouse order endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apps.mw.src.db.models import DeliveryOrderStatus


class APIModel(BaseModel):
    """Base model enabling ORM mode with enum serialisation."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, use_enum_values=True)


class WWOrderCreate(APIModel):
    """Payload accepted when creating a Walking Warehouse order."""

    external_id: str = Field(description="Identifier of the order in the upstream system.")
    status: DeliveryOrderStatus = Field(
        default=DeliveryOrderStatus.DRAFT,
        description="Initial status assigned to the order.",
    )
    courier_id: str | None = Field(
        default=None,
        description="Identifier of the courier currently responsible for the order.",
    )
    payload: dict[str, Any] | None = Field(
        default=None,
        description="Arbitrary metadata describing the order.",
    )
    actor: str = Field(description="Actor triggering the creation event.")


class WWOrderUpdate(APIModel):
    """Payload to mutate an existing Walking Warehouse order."""

    courier_id: str | None = Field(
        default=None,
        description="Updated courier identifier for the order.",
    )
    payload: dict[str, Any] | None = Field(
        default=None,
        description="Replacement metadata for the order.",
    )
    actor: str = Field(description="Actor performing the update.")


class WWOrderAssign(APIModel):
    """Payload to assign a courier to an order."""

    courier_id: str = Field(description="Identifier of the courier taking the order.")
    actor: str = Field(description="Actor assigning the order.")


class WWOrderStatusChange(APIModel):
    """Payload to change the status of an order."""

    status: DeliveryOrderStatus = Field(description="New status of the order.")
    reason: str | None = Field(
        default=None,
        description="Optional reason describing the status transition.",
    )
    actor: str = Field(description="Actor changing the status.")


class WWOrder(APIModel):
    """Order representation returned by the API."""

    id: str = Field(description="Primary identifier of the Walking Warehouse order.")
    external_id: str = Field(description="Identifier in the source system.")
    status: DeliveryOrderStatus = Field(description="Current status of the order.")
    courier_id: str | None = Field(
        default=None,
        description="Assigned courier identifier, if any.",
    )
    payload: dict[str, Any] | None = Field(
        default=None,
        description="Metadata associated with the order.",
    )
    created_at: datetime = Field(description="Creation timestamp in UTC.")
    updated_at: datetime = Field(description="Last update timestamp in UTC.")


class DeliveryLogEntry(APIModel):
    """Single event captured in the delivery log."""

    id: int = Field(description="Identifier of the log entry.")
    order_id: str = Field(description="Identifier of the order the event belongs to.")
    actor: str = Field(description="Actor responsible for the event.")
    action: str = Field(description="Machine readable action name.")
    payload: dict[str, Any] | None = Field(
        default=None,
        description="Structured payload describing the event.",
    )
    created_at: datetime = Field(description="Timestamp when the log entry was created.")
