"""Pydantic models for system and returns API responses."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ...db.models import ReturnLineQuality, ReturnSource, ReturnStatus


class Health(BaseModel):
    """Schema describing the health-check payload."""

    status: str = Field(description="Overall health status of the middleware.")
    version: str | None = Field(
        default=None,
        description="Currently deployed API version.",
    )
    uptime_seconds: int | None = Field(
        default=None,
        ge=0,
        description="Uptime of the service in seconds.",
    )


class Ping(BaseModel):
    """Schema returned by the system ping endpoint."""

    status: str = Field(description="Short status indicator.")
    timestamp: datetime = Field(description="UTC timestamp of the ping response.")
    service: str = Field(description="Identifier of the service responding to the ping.")
    checks: dict[str, str] = Field(
        default_factory=dict,
        description="Statuses of dependent subsystems (database, cache, etc.).",
    )


class ErrorItem(BaseModel):
    """Detailed description of a single validation error."""

    field: str | None = Field(
        default=None,
        description="Field path related to the error.",
    )
    message: str = Field(description="Description of the validation issue.")


class Error(BaseModel):
    """Problem+JSON compatible error representation."""

    type: str = Field(description="Link to a document describing the error type.")
    title: str = Field(description="Short human-readable summary of the error.")
    status: int = Field(description="HTTP status code applicable to this problem.")
    detail: str | None = Field(
        default=None,
        description="Explanation specific to this occurrence of the problem.",
    )
    errors: list[ErrorItem] | None = Field(
        default=None,
        description="List of field level validation errors.",
    )
    request_id: str | None = Field(
        default=None,
        description="Identifier correlating the error with logs and traces.",
    )


class ReturnLinePayload(BaseModel):
    """Base payload used for creating or updating return lines."""

    model_config = ConfigDict(use_enum_values=True)

    line_id: str = Field(description="Identifier of the line item inside the return.")
    sku: str = Field(description="Stock keeping unit of the returned product.")
    qty: Decimal = Field(gt=0, description="Quantity being returned.")
    quality: ReturnLineQuality = Field(description="Quality of the returned item.")
    reason_id: UUID | None = Field(
        default=None,
        description="Identifier of the reason linked to the return line.",
    )
    reason_note: str | None = Field(
        default=None,
        description="Additional human-readable note for the reason.",
    )
    photos: list[str] | None = Field(
        default=None,
        description="Related photo identifiers from upstream systems.",
    )
    imei: str | None = Field(
        default=None,
        description="IMEI of the returned device when applicable.",
    )
    serial: str | None = Field(
        default=None,
        description="Serial number of the returned device.",
    )


class ReturnCreate(BaseModel):
    """Request payload used when creating or updating a return."""

    model_config = ConfigDict(use_enum_values=True)

    source: ReturnSource = Field(description="Channel that initiated the return.")
    courier_id: str = Field(
        description="Identifier of the courier who collected the items from the customer.",
    )
    order_id_1c: str | None = Field(
        default=None,
        description="Optional reference to the original order in 1C.",
    )
    manager_id: str | None = Field(
        default=None,
        description="Identifier of the manager who processed the return.",
    )
    comment: str | None = Field(
        default=None,
        description="Additional notes for operators.",
    )
    status: ReturnStatus | None = Field(
        default=None,
        description="Explicit status override for the return.",
    )
    items: list[ReturnLinePayload] = Field(
        min_length=1,
        description="Items included in the return.",
    )


class ReturnLine(ReturnLinePayload):
    """Return line representation exposed in API responses."""

    model_config = ConfigDict(from_attributes=True)


class Return(BaseModel):
    """Representation of a return exposed in API responses."""

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    return_id: UUID = Field(alias="id", description="Unique identifier of the return.")
    status: ReturnStatus = Field(description="Current status of the return.")
    source: ReturnSource = Field(description="Channel that initiated the return.")
    courier_id: str = Field(description="Identifier of the courier handling the order.")
    order_id_1c: str | None = Field(
        default=None,
        description="Optional reference to the order in 1C.",
    )
    manager_id: str | None = Field(
        default=None,
        description="Identifier of the manager assigned to the return.",
    )
    comment: str | None = Field(
        default=None,
        description="Additional notes about the return.",
    )
    created_at: datetime = Field(description="When the return was created.")
    updated_at: datetime = Field(description="When the return was last updated.")
    items: list[ReturnLine] = Field(description="Items included in the return.")


class PaginatedReturns(BaseModel):
    """Paginated list of returns."""

    items: list[Return] = Field(description="Page of returns.")
    page: int = Field(ge=1, description="Current page number.")
    page_size: int = Field(ge=1, le=100, description="Number of items per page.")
    total_items: int = Field(ge=0, description="Total number of returns available.")
    total_pages: int = Field(ge=0, description="Total number of pages available.")
    has_next: bool = Field(description="Indicates if there is another page after the current one.")

