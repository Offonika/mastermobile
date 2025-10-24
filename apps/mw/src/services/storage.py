"""Storage service abstraction for call recordings."""
from __future__ import annotations

import hashlib
from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import boto3
from botocore.exceptions import ClientError
from loguru import logger

from apps.mw.src.config import get_settings
from apps.mw.src.config.settings import Settings


@dataclass(slots=True)
class StorageResult:
    """Metadata about a stored recording."""

    path: str
    checksum: str
    backend: Literal["local", "s3"]
    bytes_stored: int


@dataclass(slots=True)
class CleanupReport:
    """Summary of files removed during a cleanup run."""

    removed_local_paths: list[str]
    removed_s3_keys: list[str]

    @property
    def total_removed(self) -> int:
        return len(self.removed_local_paths) + len(self.removed_s3_keys)


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
        record_identifier: str,
    ) -> StorageResult:
        """Persist the incoming recording stream and return its metadata."""

        key = self._build_object_key(call_id, record_identifier, started_at)

        if self._backend == "s3":
            return await self._store_s3(key, stream)

        return await self._store_local(key, stream)

    def store_summary(
        self,
        call_id: str,
        content: str,
        *,
        created_at: datetime | None = None,
    ) -> StorageResult:
        """Persist a Markdown summary for a call and return its metadata."""

        created_at = created_at or datetime.now(tz=UTC)
        key = self._build_summary_key(call_id, created_at)
        payload = content.encode("utf-8")

        return self._store_bytes(key, payload)

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

    def _store_bytes(self, key: str, payload: bytes) -> StorageResult:
        if self._backend == "s3":
            return self._store_s3_bytes(key, payload)

        return self._store_local_bytes(key, payload)

    def _store_local_bytes(self, key: str, payload: bytes) -> StorageResult:
        destination = Path(self._settings.local_storage_dir) / key
        destination.parent.mkdir(parents=True, exist_ok=True)

        checksum = hashlib.sha256(payload).hexdigest()
        destination.write_bytes(payload)

        return StorageResult(
            path=str(destination),
            checksum=checksum,
            backend="local",
            bytes_stored=len(payload),
        )

    def _store_s3_bytes(self, key: str, payload: bytes) -> StorageResult:
        client = self._s3_client or self._create_s3_client()
        checksum = hashlib.sha256(payload).hexdigest()

        client.put_object(
            Bucket=self._settings.s3_bucket,
            Key=key,
            Body=payload,
        )

        return StorageResult(
            path=f"s3://{self._settings.s3_bucket}/{key}",
            checksum=checksum,
            backend="s3",
            bytes_stored=len(payload),
        )

    def cleanup_expired_assets(self, *, now: datetime | None = None) -> CleanupReport:
        """Remove recordings, transcripts and summaries past their retention window."""

        now = now or datetime.now(tz=UTC)
        removed_local: list[str] = []
        removed_s3: list[str] = []

        removed_local.extend(
            self._cleanup_local_directory(
                Path(self._settings.local_storage_dir) / "raw",
                self._settings.raw_recording_retention_days,
                now,
            )
        )
        removed_local.extend(
            self._cleanup_local_directory(
                Path(self._settings.local_storage_dir) / "summaries",
                self._settings.summary_retention_days,
                now,
            )
        )
        removed_local.extend(
            self._cleanup_local_directory(
                Path(self._settings.local_storage_dir) / "transcripts",
                self._settings.transcript_retention_days,
                now,
            )
        )

        if self._backend == "s3":
            removed_s3.extend(
                self._cleanup_s3_prefix("raw/", self._settings.raw_recording_retention_days, now)
            )
            removed_s3.extend(
                self._cleanup_s3_prefix(
                    "summaries/",
                    self._settings.summary_retention_days,
                    now,
                )
            )
            removed_s3.extend(
                self._cleanup_s3_prefix(
                    "transcripts/",
                    self._settings.transcript_retention_days,
                    now,
                )
            )

        return CleanupReport(removed_local_paths=removed_local, removed_s3_keys=removed_s3)

    def _cleanup_local_directory(
        self, directory: Path, retention_days: int, now: datetime
    ) -> list[str]:
        if retention_days <= 0:
            return []

        removed: list[str] = []
        if not directory.exists():
            return removed

        threshold = now - timedelta(days=retention_days)
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            except FileNotFoundError:
                continue

            if modified < threshold:
                try:
                    path.unlink(missing_ok=True)
                    removed.append(str(path))
                except FileNotFoundError:
                    continue
                except OSError:
                    logger.bind(path=str(path)).exception("Failed to remove expired file")

        self._remove_empty_directories(directory)
        return removed

    def _remove_empty_directories(self, root: Path) -> None:
        if not root.exists():
            return

        for directory in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                continue

    def _cleanup_s3_prefix(
        self, prefix: str, retention_days: int, now: datetime
    ) -> list[str]:
        if retention_days <= 0:
            return []

        client = self._s3_client or self._create_s3_client()
        threshold = now - timedelta(days=retention_days)
        removed: list[str] = []

        continuation_token: str | None = None
        while True:
            request: dict[str, Any] = {
                "Bucket": self._settings.s3_bucket,
                "Prefix": prefix,
            }
            if continuation_token:
                request["ContinuationToken"] = continuation_token

            response = client.list_objects_v2(**request)
            contents = response.get("Contents", []) or []
            for obj in contents:
                key = obj.get("Key")
                last_modified: datetime | None = obj.get("LastModified")
                if not key or last_modified is None:
                    continue
                moment = last_modified.astimezone(UTC)
                if moment < threshold:
                    try:
                        client.delete_object(Bucket=self._settings.s3_bucket, Key=key)
                        removed.append(key)
                    except ClientError:
                        logger.bind(key=key).exception("Failed to delete expired S3 object")

            if not response.get("IsTruncated"):
                break

            continuation_token = response.get("NextContinuationToken")
            if not continuation_token:
                break

        return removed

    def _build_object_key(
        self,
        call_id: str,
        record_identifier: str,
        started_at: datetime | None,
    ) -> str:
        if started_at is not None:
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            day = started_at.astimezone(UTC).date()
        else:
            day = datetime.now(tz=UTC).date()

        sanitized_call_id = self._sanitize_identifier(call_id)
        suffix = self._sanitize_identifier(record_identifier)

        return str(
            Path("raw")
            / f"{day.year:04d}"
            / f"{day.month:02d}"
            / f"{day.day:02d}"
            / f"call_{sanitized_call_id}_{suffix}.mp3"
        )

    def _build_summary_key(self, call_id: str, created_at: datetime) -> str:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        moment = created_at.astimezone(UTC)
        sanitized_call_id = self._sanitize_identifier(call_id) or "unknown"
        timestamp = moment.strftime("%Y%m%dT%H%M%SZ")

        return str(
            Path("summaries")
            / f"{moment.year:04d}"
            / f"{moment.month:02d}"
            / f"{moment.day:02d}"
            / f"call_{sanitized_call_id}_{timestamp}.md"
        )

    def _sanitize_identifier(self, identifier: str) -> str:
        """Normalize identifier so it can be safely used in object keys."""

        sanitized = "".join(
            char if char.isalnum() or char in {"-", "_"} else "-"
            for char in identifier
        ).strip("-_")

        if not sanitized:
            return hashlib.sha256(identifier.encode("utf-8")).hexdigest()

        return sanitized

    def _create_s3_client(self) -> Any:
        return boto3.client(
            "s3",
            endpoint_url=self._settings.s3_endpoint_url,
            region_name=self._settings.s3_region,
            aws_access_key_id=self._settings.s3_access_key_id,
            aws_secret_access_key=self._settings.s3_secret_access_key,
        )
