from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from uuid import uuid4

import httpx
import pytest
from prometheus_client import REGISTRY

from apps.mw.src.db.models import CallDirection, CallRecord, CallRecordStatus
from apps.mw.src.integrations.b24.client import MAX_RETRY_ATTEMPTS
from apps.mw.src.services.call_download import download_call_record
from apps.mw.src.services.storage import StorageResult


class _StubStorage:
    async def store_call_recording(
        self,
        call_id: str,
        stream: AsyncIterable[bytes],
        *,
        started_at,
        record_identifier: str,
    ) -> StorageResult:
        payload = bytearray()
        async for chunk in stream:
            payload.extend(chunk)
        return StorageResult(
            path=f"/tmp/{call_id}",
            checksum="deadbeef",
            backend="local",
            bytes_stored=len(payload),
        )


async def _dummy_stream() -> AsyncIterator[bytes]:
    yield b"payload"


def _metric_value(name: str, labels: dict[str, str]) -> float:
    value = REGISTRY.get_sample_value(name, labels)
    return 0.0 if value is None else value


def _build_record(**kwargs) -> CallRecord:
    defaults = dict(
        run_id=uuid4(),
        call_id="call-1",
        direction=CallDirection.INBOUND,
        from_number="123",
        to_number="456",
        duration_sec=0,
        status=CallRecordStatus.PENDING,
        recording_url="https://example.com/recording.wav",
        attempts=0,
    )
    defaults.update(kwargs)
    return CallRecord(**defaults)


@pytest.mark.asyncio
async def test_download_success_updates_metrics() -> None:
    record = _build_record()
    storage = _StubStorage()

    success_before = _metric_value("call_export_downloads_total", {"status": "success"})
    count_before = _metric_value(
        "call_export_download_duration_seconds_count",
        {"status": "success"},
    )

    result = await download_call_record(
        record,
        storage=storage,
        stream_factory=lambda *_: _dummy_stream(),
    )

    assert result is not None
    assert record.status == CallRecordStatus.DOWNLOADED
    assert (
        _metric_value("call_export_downloads_total", {"status": "success"})
        == success_before + 1.0
    )
    assert (
        _metric_value(
            "call_export_download_duration_seconds_count",
            {"status": "success"},
        )
        == count_before + 1.0
    )


@pytest.mark.asyncio
async def test_download_skip_updates_metrics() -> None:
    record = _build_record(storage_path="/tmp/file", checksum="abc123")

    skipped_before = _metric_value("call_export_downloads_total", {"status": "skipped"})

    result = await download_call_record(record)

    assert result is None
    assert (
        _metric_value("call_export_downloads_total", {"status": "skipped"})
        == skipped_before + 1.0
    )


@pytest.mark.asyncio
async def test_download_failure_updates_metrics() -> None:
    record = _build_record()

    error_before = _metric_value("call_export_downloads_total", {"status": "error"})
    count_before = _metric_value(
        "call_export_download_duration_seconds_count",
        {"status": "error"},
    )

    async def _failing_stream(*_args, **_kwargs):
        raise httpx.ConnectTimeout("boom")
        yield b""  # pragma: no cover - required to make this an async generator

    with pytest.raises(httpx.ConnectTimeout):
        await download_call_record(
            record,
            storage=_StubStorage(),
            stream_factory=_failing_stream,
        )

    assert record.status == CallRecordStatus.ERROR
    assert (
        _metric_value("call_export_downloads_total", {"status": "error"})
        == error_before + 1.0
    )
    assert (
        _metric_value(
            "call_export_download_duration_seconds_count",
            {"status": "error"},
        )
        == count_before + 1.0
    )


@pytest.mark.asyncio
async def test_download_retry_counter_updates() -> None:
    record = _build_record(attempts=1)

    retry_before = _metric_value(
        "call_export_retry_total", {"stage": "download", "reason": "retry"}
    )

    await download_call_record(
        record,
        storage=_StubStorage(),
        stream_factory=lambda *_: _dummy_stream(),
    )

    assert (
        _metric_value("call_export_retry_total", {"stage": "download", "reason": "retry"})
        == retry_before + 1.0
    )


@pytest.mark.asyncio
async def test_download_max_attempts_increments_metrics() -> None:
    record = _build_record(attempts=MAX_RETRY_ATTEMPTS)

    error_before = _metric_value("call_export_downloads_total", {"status": "error"})
    exhausted_before = _metric_value(
        "call_export_retry_total", {"stage": "download", "reason": "exhausted"}
    )

    with pytest.raises(RuntimeError):
        await download_call_record(record)

    assert (
        _metric_value("call_export_downloads_total", {"status": "error"})
        == error_before + 1.0
    )
    assert (
        _metric_value(
            "call_export_retry_total",
            {"stage": "download", "reason": "exhausted"},
        )
        == exhausted_before + 1.0
    )
