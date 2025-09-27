"""Storage service abstraction for call recordings."""
from __future__ import annotations

import hashlib
from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import boto3

from apps.mw.src.config import get_settings
from apps.mw.src.config.settings import Settings


@dataclass(slots=True)
class StorageResult:
    """Metadata about a stored recording."""

    path: str
    checksum: str
    backend: Literal["local", "s3"]
    bytes_stored: int


class StorageService:
    """Persist Bitrix24 recordings to the configured storage backend."""

    def __init__(self, settings: Settings | None = None, *, s3_client: Any | None = None) -> None:
        self._settings = settings or get_settings()
        self._backend = self._settings.storage_backend
        self._s3_client = s3_client
        if self._backend == "s3" and not self._settings.s3_bucket:
            raise ValueError("S3 bucket must be configured for S3 storage backend")

    async def store_call_recording(
        self,
        call_id: str,
        stream: AsyncIterable[bytes],
        *,
        started_at: datetime | None,
    ) -> StorageResult:
        """Persist the incoming recording stream and return its metadata."""

        key = self._build_object_key(call_id, started_at)

        if self._backend == "s3":
            return await self._store_s3(key, stream)

        return await self._store_local(key, stream)

    async def _store_local(self, key: str, stream: AsyncIterable[bytes]) -> StorageResult:
        storage_root = Path(self._settings.local_storage_dir)
        storage_root.mkdir(parents=True, exist_ok=True)

        destination = storage_root / key
        destination.parent.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        bytes_written = 0

        with destination.open("wb") as handle:
            async for chunk in stream:
                handle.write(chunk)
                digest.update(chunk)
                bytes_written += len(chunk)

        return StorageResult(
            path=str(destination),
            checksum=digest.hexdigest(),
            backend="local",
            bytes_stored=bytes_written,
        )

    async def _store_s3(self, key: str, stream: AsyncIterable[bytes]) -> StorageResult:
        client = self._s3_client or self._create_s3_client()
        digest = hashlib.sha256()
        payload = bytearray()

        bytes_written = 0
        async for chunk in stream:
            payload.extend(chunk)
            digest.update(chunk)
            bytes_written += len(chunk)

        client.put_object(
            Bucket=self._settings.s3_bucket,
            Key=key,
            Body=bytes(payload),
        )

        return StorageResult(
            path=f"s3://{self._settings.s3_bucket}/{key}",
            checksum=digest.hexdigest(),
            backend="s3",
            bytes_stored=bytes_written,
        )

    def _build_object_key(self, call_id: str, started_at: datetime | None) -> str:
        if started_at is not None:
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            day = started_at.astimezone(timezone.utc).date()
        else:
            day = datetime.now(tz=timezone.utc).date()

        return str(
            Path("raw")
            / f"{day.year:04d}"
            / f"{day.month:02d}"
            / f"{day.day:02d}"
            / f"call_{call_id}.mp3"
        )

    def _create_s3_client(self) -> Any:
        return boto3.client(
            "s3",
            endpoint_url=self._settings.s3_endpoint_url,
            region_name=self._settings.s3_region,
            aws_access_key_id=self._settings.s3_access_key_id,
            aws_secret_access_key=self._settings.s3_secret_access_key,
        )
