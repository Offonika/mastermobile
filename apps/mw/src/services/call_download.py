"""Workflow helpers for downloading Bitrix24 call recordings."""
from __future__ import annotations

import hashlib
from collections.abc import AsyncIterable
from datetime import datetime, timezone
from typing import Callable

import httpx
from loguru import logger

from apps.mw.src.db.models import CallRecord, CallRecordStatus
from apps.mw.src.domain import register_http_failure
from apps.mw.src.integrations.b24.client import MAX_RETRY_ATTEMPTS
from apps.mw.src.integrations.b24.downloader import stream_recording
from apps.mw.src.services.storage import StorageResult, StorageService


RecordingStreamFactory = Callable[[str, str | None], AsyncIterable[bytes]]


async def download_call_record(
    record: CallRecord,
    *,
    storage: StorageService | None = None,
    stream_factory: RecordingStreamFactory = stream_recording,
) -> StorageResult | None:
    """Download a call recording and persist it using the configured storage backend."""

    if record.storage_path and record.checksum:
        logger.bind(
            event="call_export.download",
            stage="skipped",
            call_id=record.call_id,
            attempt=record.attempts,
        ).info("Call already downloaded")
        return None

    if record.attempts >= MAX_RETRY_ATTEMPTS:
        if record.status is not CallRecordStatus.MISSING_AUDIO:
            record.status = CallRecordStatus.ERROR
            record.error_code = "max_attempts"
            record.error_message = "Maximum download attempts exceeded"
        record.last_attempt_at = datetime.now(tz=timezone.utc)
        logger.bind(
            event="call_export.download",
            stage="max_retries",
            call_id=record.call_id,
            attempt=record.attempts,
            max_attempts=MAX_RETRY_ATTEMPTS,
        ).error("Maximum download attempts exceeded")
        raise RuntimeError("maximum download attempts exceeded")

    storage = storage or StorageService()

    record.status = CallRecordStatus.DOWNLOADING
    record.last_attempt_at = datetime.now(tz=timezone.utc)
    attempt_number = record.attempts + 1
    logger.bind(
        event="call_export.download",
        stage="start",
        call_id=record.call_id,
        attempt=attempt_number,
    ).info("Starting call download")

    try:
        stream = stream_factory(record.call_id, record.record_id)
        result = await storage.store_call_recording(
            record.call_id,
            stream,
            started_at=record.call_started_at,
            record_identifier=_resolve_record_identifier(record),
        )
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive guard
        _register_http_failure(record, exc)
        raise
    except httpx.HTTPError as exc:
        _handle_failure(record, exc.__class__.__name__, str(exc))
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        _handle_failure(record, exc.__class__.__name__, str(exc))
        raise

    record.attempts = attempt_number
    record.storage_path = result.path
    record.checksum = result.checksum
    record.status = CallRecordStatus.DOWNLOADED
    record.error_code = None
    record.error_message = None

    logger.bind(
        event="call_export.download",
        stage="completed",
        call_id=record.call_id,
        attempt=record.attempts,
        storage_backend=result.backend,
        bytes_stored=result.bytes_stored,
    ).info("Finished call download")

    return result


def _handle_failure(record: CallRecord, code: str, message: str) -> None:
    record.attempts += 1
    record.last_attempt_at = datetime.now(tz=timezone.utc)
    record.status = CallRecordStatus.ERROR
    record.error_code = code
    record.error_message = message
    _log_failure(record, code)


def _register_http_failure(record: CallRecord, exc: httpx.HTTPStatusError) -> None:
    status_code = exc.response.status_code
    register_http_failure(
        record,
        status_code=status_code,
        message=str(exc),
        max_attempts=MAX_RETRY_ATTEMPTS,
    )
    _log_failure(record, f"http_{status_code}")


def _log_failure(record: CallRecord, code: str) -> None:
    logger.bind(
        event="call_export.download",
        stage="error",
        call_id=record.call_id,
        attempt=record.attempts,
        error_code=code,
    ).error("Failed to download call")


def _resolve_record_identifier(record: CallRecord) -> str:
    """Return a stable identifier for storage paths for the given record."""

    if record.record_id and record.record_id.strip():
        return record.record_id.strip()

    if record.recording_url:
        return hashlib.sha256(record.recording_url.encode("utf-8")).hexdigest()

    return hashlib.sha256(record.call_id.encode("utf-8")).hexdigest()
