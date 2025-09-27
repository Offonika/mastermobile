"""Helpers for tracking Bitrix24 call recording download attempts."""

from __future__ import annotations

from datetime import datetime, timezone

from apps.mw.src.db.models import CallRecord, CallRecordStatus

MISSING_AUDIO_HTTP_STATUS = {403, 404}
DEFAULT_MAX_ATTEMPTS = 5


def _now_utc() -> datetime:
    """Return timezone-aware timestamp for bookkeeping fields."""

    return datetime.now(timezone.utc)


def register_http_failure(
    record: CallRecord,
    *,
    status_code: int,
    message: str | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> None:
    """Persist the outcome of a failed download attempt on the ORM entity."""

    record.retry_count += 1
    record.last_retry_at = _now_utc()
    record.error_code = f"http_{status_code}"
    record.error_message = message or f"HTTP {status_code}"

    if status_code in MISSING_AUDIO_HTTP_STATUS and record.retry_count >= max_attempts:
        record.status = CallRecordStatus.MISSING_AUDIO
    else:
        record.status = CallRecordStatus.ERROR


__all__ = ["register_http_failure", "DEFAULT_MAX_ATTEMPTS", "MISSING_AUDIO_HTTP_STATUS"]
