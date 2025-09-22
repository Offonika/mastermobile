"""Pydantic representations for system and return API payloads."""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from apps.mw.src.db.models import ReturnLineQuality, ReturnSource, ReturnStatus


class APIModel(BaseModel):
    """Base class enabling ORM serialisation helpers."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, use_enum_values=True)


class Health(APIModel):
    """Schema describing the `/health` response payload."""

    status: str = Field(description="Overall health status of the middleware.")
    version: str | None = Field(
        default=None,
        description="Currently deployed API version.",
    )
    uptime_seconds: int | None = Field(
        default=None,
        description="Uptime of the service in seconds.",
    )


class Ping(APIModel):
    """Schema returned by `/api/v1/system/ping`."""

    status: str = Field(description="Short status indicator.")
    timestamp: datetime = Field(description="UTC timestamp of the ping response.")
    service: str | None = Field(
        default=None,
        description="Identifier of the service responding to the ping.",
    )


class Error(APIModel):
    """Problem Details object returned on API failures."""

    type: str = Field(description="URI identifying the error type.")
    title: str = Field(description="Short human readable summary of the error.")
    status: int = Field(description="HTTP status code for the error response.")
    detail: str | None = Field(
        default=None,
        description="Human readable explanation specific to this occurrence.",
    )
    errors: list[dict[str, str]] | None = Field(
        default=None,
        description="Optional list of field level validation errors.",
    )
    request_id: str | None = Field(
        default=None,
        description="Identifier correlating the request with logs and traces.",
    )


class ReturnItem(APIModel):
    """Line item persisted for a return document."""

    line_id: str = Field(description="Identifier of the line item inside the return.")
    sku: str = Field(description="Stock keeping unit of the returned product.")
    qty: int = Field(ge=1, description="Quantity being returned.")
    quality: ReturnLineQuality = Field(description="Quality of the returned item.")
    reason_code: str = Field(description="Machine readable reason code.")
    reason_note: str | None = Field(
        default=None,
        description="Additional human readable note for the reason.",
    )
    photos: list[str] | None = Field(
        default=None,
        description="Bitrix24 file identifiers for related photos.",
    )
    imei: str | None = Field(
        default=None,
        description="IMEI of the returned device when applicable.",
    )
    serial: str | None = Field(
        default=None,
        description="Serial number of the returned device.",
    )


class Return(APIModel):
    """Return document exposed by the API."""

    id: str = Field(description="Unique identifier of the return.")
    status: ReturnStatus = Field(description="Current status of the return.")
    source: ReturnSource = Field(description="Channel that initiated the return.")
    courier_id: str = Field(description="Identifier of the courier handling the order.")
    order_id_1c: str | None = Field(
        default=None,
        description="Optional reference to the order in 1C.",
    )
    manager_id: str | None = Field(
        default=None,
        description="Identifier of the manager who processed the return.",
    )
    comment: str | None = Field(
        default=None,
        description="Additional notes about the return.",
    )
    created_at: datetime = Field(description="When the return was created.")
    updated_at: datetime = Field(description="When the return was last updated.")
    items: List[ReturnItem] = Field(
        description="Items included in the return.",
        min_length=1,
    )


class ReturnCreateItem(APIModel):
    """Input line item when creating or updating a return."""

    sku: str = Field(description="Stock keeping unit of the returned product.")
    qty: int = Field(ge=1, description="Quantity being returned.")
    quality: ReturnLineQuality = Field(description="Quality of the returned item.")
    reason_code: str = Field(description="Machine readable reason code.")
    reason_note: str | None = Field(
        default=None,
        description="Additional human readable note for the reason.",
    )
    photos: list[str] | None = Field(
        default=None,
        description="Bitrix24 file identifiers for related photos.",
    )
    imei: str | None = Field(
        default=None,
        description="IMEI of the returned device when applicable.",
    )
    serial: str | None = Field(
        default=None,
        description="Serial number of the returned device.",
    )


class ReturnCreate(APIModel):
    """Input payload for creating or updating a return."""

    source: ReturnSource = Field(description="Channel that initiated the return.")
    courier_id: str = Field(
        description="Identifier of the courier who collected the items from the customer.",
    )
    order_id_1c: str | None = Field(
        default=None,
        description="Optional reference to the original order in 1C.",
    )
    comment: str | None = Field(
        default=None,
        description="Additional notes for operators.",
    )
    items: List[ReturnCreateItem] = Field(
        description="Items being returned.",
        min_length=1,
    )


class PaginatedReturns(APIModel):
    """Paginated collection of returns."""

    items: List[Return] = Field(description="Page of returns.")
    page: int = Field(ge=1, description="Current page number.")
    page_size: int = Field(ge=1, description="Number of items per page.")
    total_items: int = Field(ge=0, description="Total number of returns available.")
    total_pages: int = Field(ge=0, description="Total number of pages available.")
    has_next: bool | None = Field(
        default=None,
        description="Indicates if there is another page after the current one.",
    )
