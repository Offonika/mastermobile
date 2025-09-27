"""Tests for Bitrix24 recording download workflow."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import boto3
import httpx
import pytest
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


def _call_record(
    status: CallRecordStatus = CallRecordStatus.PENDING, **overrides: object
) -> CallRecord:
    payload: dict[str, object] = {
        "run_id": uuid4(),
        "call_id": "42",
        "record_id": "1001",
        "call_started_at": datetime(2024, 9, 1, 12, 0, tzinfo=timezone.utc),
        "duration_sec": 120,
        "recording_url": None,
        "storage_path": None,
        "transcript_path": None,
        "transcript_lang": None,
        "checksum": None,
        "status": status,
        "attempts": 0,
    }
    payload.update(overrides)
    return CallRecord(**payload)


@pytest.mark.asyncio
async def test_stream_recording_retries_and_streams_bytes(
    respx_mock: "respx.MockRouter", sleep_mock: AsyncMock
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
        started_at=datetime(2024, 9, 2, 15, 30, tzinfo=timezone.utc),
    )

    expected_path = (
        Path(settings.local_storage_dir)
        / "raw"
        / "2024"
        / "09"
        / "02"
        / "call_abc.mp3"
    )

    assert Path(result.path) == expected_path
    assert expected_path.exists()
    assert expected_path.read_bytes() == b"hello-world"
    assert result.checksum == hashlib.sha256(b"hello-world").hexdigest()


@pytest.mark.asyncio
async def test_download_workflow_updates_status_and_checksum(
    respx_mock: "respx.MockRouter",
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
    storage_path = Path(record.storage_path)
    assert storage_path.exists()
    expected_suffix = hashlib.sha256("1001".encode("utf-8")).hexdigest()[:16]
    assert storage_path.name == f"call_42_{expected_suffix}.mp3"
    assert record.checksum == hashlib.sha256(b"binary-audio").hexdigest()
    assert record.attempts == 1
    assert record.error_code is None
    assert record.error_message is None


@pytest.mark.asyncio
async def test_download_records_with_same_call_id_use_unique_paths() -> None:
    """Different Bitrix24 recordings for one call ID persist independently."""

    record_one = _call_record(record_id="rec-1")
    record_two = _call_record(record_id="rec-2")

    storage = StorageService(settings=get_settings())

    def stream_factory(call_id: str, record_id: str | None):
        async def _gen(payload: bytes):
            yield payload

        if record_id == "rec-1":
            return _gen(b"audio-one")
        if record_id == "rec-2":
            return _gen(b"audio-two")
        raise AssertionError("unexpected record identifier")

    result_one = await download_call_record(
        record_one, storage=storage, stream_factory=stream_factory
    )
    assert record_one.storage_path is not None
    path_one = Path(record_one.storage_path)
    result_two = await download_call_record(
        record_two, storage=storage, stream_factory=stream_factory
    )
    assert record_two.storage_path is not None
    path_two = Path(record_two.storage_path)

    assert result_one is not None and result_two is not None
    assert path_one.exists() and path_two.exists()
    assert path_one != path_two
    assert path_one.read_bytes() == b"audio-one"
    assert path_two.read_bytes() == b"audio-two"

    suffix_one = hashlib.sha256("rec-1".encode("utf-8")).hexdigest()[:16]
    suffix_two = hashlib.sha256("rec-2".encode("utf-8")).hexdigest()[:16]
    assert path_one.name == f"call_42_{suffix_one}.mp3"
    assert path_two.name == f"call_42_{suffix_two}.mp3"


@pytest.mark.asyncio
async def test_download_workflow_skips_when_already_downloaded(
    respx_mock: "respx.MockRouter",
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


@pytest.mark.asyncio
async def test_download_workflow_respects_retry_limit(
    respx_mock: "respx.MockRouter",
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

    expected_key = "raw/2024/09/01/call_42.mp3"
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
        started_at=datetime(2024, 9, 1, tzinfo=timezone.utc),
    )

    stubber.deactivate()
    stubber.assert_no_pending_responses()
    assert result.path == "s3://test-bucket/raw/2024/09/01/call_42.mp3"
    assert result.checksum == hashlib.sha256(b"cloud-bytes").hexdigest()
    assert result.backend == "s3"
