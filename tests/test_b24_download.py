"""Tests for Bitrix24 recording download workflow."""
from __future__ import annotations

import hashlib
from collections.abc import AsyncIterable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import boto3
import httpx
import pytest
import respx
from botocore.stub import Stubber

from apps.mw.src.config.settings import get_settings
from apps.mw.src.db.models import CallRecord, CallRecordStatus
from apps.mw.src.integrations.b24 import stream_recording
from apps.mw.src.integrations.b24.client import MAX_RETRY_ATTEMPTS
from apps.mw.src.services.call_download import download_call_record
from apps.mw.src.services.storage import StorageService


@pytest.fixture(autouse=True)
def configure_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Configure defaults for Bitrix24 and storage related settings."""

    monkeypatch.setenv("B24_BASE_URL", "https://example.bitrix24.ru/rest")
    monkeypatch.setenv("B24_WEBHOOK_USER_ID", "1")
    monkeypatch.setenv("B24_WEBHOOK_TOKEN", "token")
    monkeypatch.setenv("B24_RATE_LIMIT_RPS", "2")
    monkeypatch.setenv("B24_BACKOFF_SECONDS", "5")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "local")

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def sleep_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patch asyncio.sleep in the downloader to avoid real delays."""

    mock = AsyncMock()
    monkeypatch.setattr("apps.mw.src.integrations.b24.downloader.asyncio.sleep", mock)
    return mock


def _call_record(status: CallRecordStatus = CallRecordStatus.PENDING) -> CallRecord:
    return CallRecord(
        run_id=uuid4(),
        call_id="42",
        record_id="1001",
        call_started_at=datetime(2024, 9, 1, 12, 0, tzinfo=UTC),
        duration_sec=120,
        recording_url=None,
        storage_path=None,
        transcript_path=None,
        language=None,
        checksum=None,
        status=status,
        attempts=0,
    )


@pytest.mark.asyncio
async def test_stream_recording_retries_and_streams_bytes(
    respx_mock: respx.MockRouter, sleep_mock: AsyncMock
) -> None:
    """Downloader applies retry/backoff logic and yields streamed data."""

    url = "https://example.bitrix24.ru/rest/1/token/telephony.recording.get"
    route = respx_mock.get(url).mock(
        side_effect=[
            httpx.Response(429, json={"error": "Too many requests"}),
            httpx.Response(200, content=b"audio-bytes"),
        ]
    )

    chunks = [chunk async for chunk in stream_recording("42")]
    data = b"".join(chunks)

    assert data == b"audio-bytes"
    assert route.call_count == 2
    assert sleep_mock.await_count == 1
    assert sleep_mock.await_args_list[0].args[0] == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_storage_local_persists_file_with_checksum(tmp_path: Path) -> None:
    """Local backend writes a deterministic path and computes checksum."""

    settings = get_settings()
    service = StorageService(settings=settings)

    async def generator():
        yield b"hello-world"

    result = await service.store_call_recording(
        "abc",
        generator(),
        started_at=datetime(2024, 9, 2, 15, 30, tzinfo=UTC),
        record_identifier="rec-abc",
    )

    expected_path = (
        Path(settings.local_storage_dir)
        / "raw"
        / "2024"
        / "09"
        / "02"
        / "call_abc_rec-abc.mp3"
    )

    assert Path(result.path) == expected_path
    assert expected_path.exists()
    assert expected_path.read_bytes() == b"hello-world"
    assert result.checksum == hashlib.sha256(b"hello-world").hexdigest()


@pytest.mark.asyncio
async def test_storage_local_sanitizes_call_id_path(tmp_path: Path) -> None:
    """Malicious call IDs cannot escape the configured storage root."""

    settings = get_settings()
    service = StorageService(settings=settings)

    async def generator():
        yield b"guarded"

    result = await service.store_call_recording(
        "../escape/../../call",
        generator(),
        started_at=datetime(2024, 9, 2, 15, 30, tzinfo=UTC),
        record_identifier="segment/../../id",
    )

    storage_root = Path(settings.local_storage_dir)
    destination = Path(result.path)

    assert destination.is_relative_to(storage_root)

    sanitized_call_id = service._sanitize_identifier("../escape/../../call")
    sanitized_record_id = service._sanitize_identifier("segment/../../id")

    expected_path = (
        storage_root
        / "raw"
        / "2024"
        / "09"
        / "02"
        / f"call_{sanitized_call_id}_{sanitized_record_id}.mp3"
    )

    assert destination == expected_path


@pytest.mark.asyncio
async def test_download_workflow_updates_status_and_checksum(
    respx_mock: respx.MockRouter,
) -> None:
    """Successful download transitions the record and stores metadata."""

    record = _call_record()

    url = "https://example.bitrix24.ru/rest/1/token/telephony.recording.get"
    respx_mock.get(url).mock(return_value=httpx.Response(200, content=b"binary-audio"))

    storage = StorageService(settings=get_settings())
    result = await download_call_record(record, storage=storage)

    assert result is not None
    assert record.status is CallRecordStatus.DOWNLOADED
    assert record.storage_path is not None
    assert Path(record.storage_path).exists()
    assert record.checksum == hashlib.sha256(b"binary-audio").hexdigest()
    assert record.attempts == 1
    assert record.error_code is None
    assert record.error_message is None


@pytest.mark.asyncio
async def test_download_workflow_skips_when_already_downloaded(
    respx_mock: respx.MockRouter,
) -> None:
    """Existing storage path and checksum prevent duplicate downloads."""

    record = _call_record(status=CallRecordStatus.DOWNLOADED)
    record.storage_path = "/tmp/fake.mp3"
    record.checksum = "deadbeef"
    record.attempts = 3

    url = "https://example.bitrix24.ru/rest/1/token/telephony.recording.get"
    route = respx_mock.get(url).mock(return_value=httpx.Response(200, content=b"unused"))

    result = await download_call_record(record, storage=StorageService(settings=get_settings()))

    assert result is None
    assert route.call_count == 0
    assert record.attempts == 3
    assert record.status is CallRecordStatus.DOWNLOADED


def _http_status_error(status_code: int, message: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.bitrix24.ru/rest/recording")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(message, request=request, response=response)


@pytest.mark.asyncio
async def test_download_marks_missing_audio_after_limit_on_404() -> None:
    """Final retry on 404 switches the record to missing audio without checksum."""

    record = _call_record(status=CallRecordStatus.ERROR)
    record.attempts = MAX_RETRY_ATTEMPTS - 1

    storage = AsyncMock(spec=StorageService)
    storage.store_call_recording = AsyncMock()

    def failing_stream_factory(call_id: str, record_id: str | None) -> AsyncIterable[bytes]:  # type: ignore[override]
        raise _http_status_error(404, "Recording not found")

    with pytest.raises(httpx.HTTPStatusError):
        await download_call_record(
            record,
            storage=storage,
            stream_factory=failing_stream_factory,
        )

    assert record.status is CallRecordStatus.MISSING_AUDIO
    assert record.attempts == MAX_RETRY_ATTEMPTS
    assert record.checksum is None
    assert record.storage_path is None
    assert record.error_code == "http_404"
    storage.store_call_recording.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_marks_missing_audio_after_limit_on_403() -> None:
    """Forbidden response after exhausting retries marks the record as missing audio."""

    record = _call_record(status=CallRecordStatus.ERROR)
    record.attempts = MAX_RETRY_ATTEMPTS - 1

    storage = AsyncMock(spec=StorageService)
    storage.store_call_recording = AsyncMock()

    def failing_stream_factory(call_id: str, record_id: str | None) -> AsyncIterable[bytes]:  # type: ignore[override]
        raise _http_status_error(403, "Forbidden")

    with pytest.raises(httpx.HTTPStatusError):
        await download_call_record(
            record,
            storage=storage,
            stream_factory=failing_stream_factory,
        )

    assert record.status is CallRecordStatus.MISSING_AUDIO
    assert record.attempts == MAX_RETRY_ATTEMPTS
    assert record.checksum is None
    assert record.storage_path is None
    assert record.error_code == "http_403"
    storage.store_call_recording.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_records_with_same_call_id_store_distinct_files() -> None:
    """Different Bitrix recordings for the same call ID keep separate files."""

    first = _call_record()
    second = _call_record()
    second.record_id = "1002"

    payloads = {
        (first.call_id, first.record_id): b"first-audio",
        (second.call_id, second.record_id): b"second-audio",
    }

    async def fake_stream(call_id: str, record_id: str | None):
        yield payloads[(call_id, record_id)]

    storage = StorageService(settings=get_settings())

    result_first = await download_call_record(
        first,
        storage=storage,
        stream_factory=fake_stream,
    )
    result_second = await download_call_record(
        second,
        storage=storage,
        stream_factory=fake_stream,
    )

    assert result_first is not None
    assert result_second is not None
    assert result_first.path != result_second.path
    assert Path(result_first.path).read_bytes() == b"first-audio"
    assert Path(result_second.path).read_bytes() == b"second-audio"


@pytest.mark.asyncio
async def test_download_workflow_respects_retry_limit(
    respx_mock: respx.MockRouter,
) -> None:
    """Records stop processing once the maximum retry limit is reached."""

    record = _call_record()
    record.attempts = MAX_RETRY_ATTEMPTS

    url = "https://example.bitrix24.ru/rest/1/token/telephony.recording.get"
    route = respx_mock.get(url).mock(return_value=httpx.Response(200, content=b"unused"))

    with pytest.raises(RuntimeError):
        await download_call_record(record, storage=StorageService(settings=get_settings()))

    assert route.call_count == 0
    assert record.status is CallRecordStatus.ERROR
    assert record.error_code == "max_attempts"


@pytest.mark.asyncio
async def test_storage_s3_backend_uses_configured_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S3 backend uploads to the configured bucket and returns metadata."""

    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_REGION", "us-east-1")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret")
    get_settings.cache_clear()

    client = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="key",
        aws_secret_access_key="secret",
    )
    stubber = Stubber(client)

    expected_key = "raw/2024/09/01/call_42_1001.mp3"
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": "test-bucket",
            "Key": expected_key,
            "Body": b"cloud-bytes",
        },
    )

    stubber.activate()

    service = StorageService(settings=get_settings(), s3_client=client)

    async def generator():
        yield b"cloud-bytes"

    result = await service.store_call_recording(
        "42",
        generator(),
        started_at=datetime(2024, 9, 1, tzinfo=UTC),
        record_identifier="1001",
    )

    stubber.deactivate()
    stubber.assert_no_pending_responses()
    assert result.path == "s3://test-bucket/raw/2024/09/01/call_42_1001.mp3"
    assert result.checksum == hashlib.sha256(b"cloud-bytes").hexdigest()
    assert result.backend == "s3"
