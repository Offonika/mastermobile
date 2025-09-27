"""Schemas for STT administration endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class STTJobPayload(BaseModel):
    """Serialized representation of a Speech-to-Text job."""

    record_id: int
    call_id: str
    recording_url: str
    engine: str
    language: str | None = None


class STTDLQRequeueResponse(BaseModel):
    """Response returned after successfully requeueing a DLQ job."""

    status: Literal["requeued"]
    entry_id: str
    job: STTJobPayload
    reason: str
    failed_at: datetime
    status_code: int | None = None
