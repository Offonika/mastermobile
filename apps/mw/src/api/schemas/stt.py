from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class STTAPIModel(BaseModel):
    """Base schema for STT-related payloads."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DLQReplayRequest(STTAPIModel):
    """Request payload for replaying a job from the DLQ."""

    record_id: int = Field(
        ge=1,
        description="Identifier of the call record associated with the STT job.",
    )
    reason: str = Field(
        min_length=1,
        max_length=1024,
        description="Operator provided reason for replaying the job.",
    )


class DLQReplayResponse(STTAPIModel):
    """Response body confirming that a DLQ job was replayed."""

    status: str = Field(description="Outcome of the replay request.")
    job: dict[str, Any] = Field(
        description="Payload of the STT job that was re-enqueued.",
    )
