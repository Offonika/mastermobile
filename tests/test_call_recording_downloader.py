"""Unit tests for the Bitrix24 call recording download helpers."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from apps.mw.src.db.models import CallRecord, CallRecordStatus
from apps.mw.src.domain import register_http_failure


def _make_record(*, attempts: int, status: CallRecordStatus = CallRecordStatus.DOWNLOADING) -> CallRecord:
    return CallRecord(
        run_id=uuid4(),
        call_id="CALL-001",
        duration_sec=120,
        status=status,
        recording_url="https://example.com/audio.wav",
        attempts=attempts,
    )


def test_register_http_failure_marks_missing_audio_after_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """When attempts hit the ceiling on 404 the record is marked as missing audio."""

    record = _make_record(attempts=4)
    frozen_now = datetime(2024, 10, 1, 12, 0, 0)
    monkeypatch.setattr(
        "apps.mw.src.domain.call_recording_downloader._now_utc",
        lambda: frozen_now,
    )

    register_http_failure(record, status_code=404, message="Recording not found", max_attempts=5)

    assert record.status is CallRecordStatus.MISSING_AUDIO
    assert record.attempts == 5
    assert record.error_code == "http_404"
    assert record.error_message == "Recording not found"
    assert record.last_attempt_at == frozen_now


def test_register_http_failure_keeps_error_before_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Before the limit 403 responses keep the record in ``error`` for retry."""

    record = _make_record(attempts=1)
    frozen_now = datetime(2024, 10, 1, 13, 0, 0)
    monkeypatch.setattr(
        "apps.mw.src.domain.call_recording_downloader._now_utc",
        lambda: frozen_now,
    )

    register_http_failure(record, status_code=403, message="Forbidden", max_attempts=5)

    assert record.status is CallRecordStatus.ERROR
    assert record.attempts == 2
    assert record.error_code == "http_403"
    assert record.error_message == "Forbidden"
    assert record.last_attempt_at == frozen_now
