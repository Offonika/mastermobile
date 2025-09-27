"""Workflow helpers for downloading Bitrix24 call recordings."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterable
from datetime import datetime, timezone
from typing import Callable

import httpx

from apps.mw.src.db.models import CallRecord, CallRecordStatus
from apps.mw.src.integrations.b24.client import MAX_RETRY_ATTEMPTS
from apps.mw.src.integrations.b24.downloader import stream_recording
from apps.mw.src.services.storage import StorageResult, StorageService

logger = logging.getLogger(__name__)


RecordingStreamFactory = Callable[[str, str | None], AsyncIterable[bytes]]


async def download_call_record(
    record: CallRecord,
    *,
    storage: StorageService | None = None,
    stream_factory: RecordingStreamFactory = stream_recording,
) -> StorageResult | None:
    """Download a call recording and persist it using the configured storage backend."""

    if record.storage_path and record.checksum:
        logger.info(
            "Call %s already downloaded; skipping", record.call_id
        )
        return None

    if record.attempts >= MAX_RETRY_ATTEMPTS:
        record.status = CallRecordStatus.ERROR
        record.error_code = "max_attempts"
        record.error_message = "Maximum download attempts exceeded"
        record.last_attempt_at = datetime.now(tz=timezone.utc)
        logger.error(
            "Call %s exceeded retry limit; attempts=%s", record.call_id, record.attempts
        )
        raise RuntimeError("maximum download attempts exceeded")

    storage = storage or StorageService()

    record.status = CallRecordStatus.DOWNLOADING
    record.attempts += 1
    record.last_attempt_at = datetime.now(tz=timezone.utc)
    logger.info("Starting download for call %s", record.call_id)

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

    logger.info(
        "Finished download for call %s (backend=%s, bytes=%s)",
        record.call_id,
        result.backend,
        result.bytes_stored,
    )

    return result


def _handle_failure(record: CallRecord, code: str, message: str) -> None:
    record.status = CallRecordStatus.ERROR
    record.error_code = code
    record.error_message = message
    logger.error(
        "Failed to download call %s (attempt=%s): %s", record.call_id, record.attempts, message
    )
