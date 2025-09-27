"""Workflow helpers for downloading Bitrix24 call recordings."""
from __future__ import annotations

from collections.abc import AsyncIterable
from datetime import datetime, timezone
from typing import Callable

import httpx
from loguru import logger

from apps.mw.src.db.models import CallRecord, CallRecordStatus
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
    record.attempts += 1
    record.last_attempt_at = datetime.now(tz=timezone.utc)
    logger.bind(
        event="call_export.download",
        stage="start",
        call_id=record.call_id,
        attempt=record.attempts,
    ).info("Starting call download")

    try:
        stream = stream_factory(record.call_id, record.record_id)
        result = await storage.store_call_recording(
            record.call_id,
            stream,
            started_at=record.call_started_at,
        )
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive guard
        _handle_failure(record, f"http_{exc.response.status_code}", str(exc))
        raise
    except httpx.HTTPError as exc:
        _handle_failure(record, exc.__class__.__name__, str(exc))
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        _handle_failure(record, exc.__class__.__name__, str(exc))
        raise

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
    record.status = CallRecordStatus.ERROR
    record.error_code = code
    record.error_message = message
    logger.bind(
        event="call_export.download",
        stage="error",
        call_id=record.call_id,
        attempt=record.attempts,
        error_code=code,
    ).error("Failed to download call")
