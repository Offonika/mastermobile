"""Schemas for ChatKit and vector store integrations."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from apps.mw.src.api.schemas.returns import APIModel


class ChatkitSession(APIModel):
    """Response payload carrying ChatKit client secret."""

    client_secret: str = Field(description="Client secret used to initialise ChatKit SDKs.")


class VectorStoreMetadata(APIModel):
    """Metadata submitted alongside uploaded documents."""

    title: str = Field(description="Human readable title of the document.")
    dept: str | None = Field(default=None, description="Department owning the document.")
    version: str | None = Field(default=None, description="Version identifier of the document.")
    updated_at: str | None = Field(default=None, description="ISO-8601 timestamp of the latest update.")
    source: str = Field(description="Source of the document data.")


class VectorStoreUploadResponse(APIModel):
    """Response confirming successful upload to the vector store."""

    status: Literal["ok"] = Field(description="Status marker of the upload operation.")
    filename: str | None = Field(default=None, description="Original filename of the uploaded document.")
    metadata: VectorStoreMetadata = Field(description="Metadata persisted in the vector store.")
