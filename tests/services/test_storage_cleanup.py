"""Tests for storage cleanup routines."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.stub import Stubber

from apps.mw.src.config.settings import Settings
from apps.mw.src.services.cleanup import StorageCleanupRunner
from apps.mw.src.services.storage import CleanupReport, StorageService


def _touch(path: Path, *, modified: datetime, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    timestamp = modified.timestamp()
    os.utime(path, (timestamp, timestamp))


def test_cleanup_expired_local_files_removed(tmp_path: Path) -> None:
    settings = Settings(
        STORAGE_BACKEND="local",
        LOCAL_STORAGE_DIR=str(tmp_path),
        RAW_RECORDING_RETENTION_DAYS=1,
        SUMMARY_RETENTION_DAYS=2,
        TRANSCRIPT_RETENTION_DAYS=3,
        STORAGE_CLEANUP_INTERVAL_HOURS=24,
    )
    service = StorageService(settings=settings)

    now = datetime.now(tz=UTC)
    old_time = now - timedelta(days=5)
    recent_time = now - timedelta(hours=2)

    raw_old = tmp_path / "raw" / "2024" / "01" / "old.mp3"
    raw_recent = tmp_path / "raw" / "2024" / "01" / "recent.mp3"
    summary_old = tmp_path / "summaries" / "2024" / "01" / "old.md"
    summary_recent = tmp_path / "summaries" / "2024" / "01" / "recent.md"
    transcript_old = tmp_path / "transcripts" / "old.txt"
    transcript_recent = tmp_path / "transcripts" / "recent.txt"

    _touch(raw_old, modified=old_time, content=b"old")
    _touch(raw_recent, modified=recent_time, content=b"new")
    _touch(summary_old, modified=now - timedelta(days=3), content=b"old summary")
    _touch(summary_recent, modified=recent_time, content=b"new summary")
    _touch(transcript_old, modified=now - timedelta(days=4), content=b"old transcript")
    _touch(transcript_recent, modified=recent_time, content=b"new transcript")

    report = service.cleanup_expired_assets(now=now)

    assert not raw_old.exists()
    assert raw_recent.exists()
    assert not summary_old.exists()
    assert summary_recent.exists()
    assert not transcript_old.exists()
    assert transcript_recent.exists()
    assert str(raw_old) in report.removed_local_paths
    assert str(summary_old) in report.removed_local_paths
    assert str(transcript_old) in report.removed_local_paths
    assert str(raw_recent) not in report.removed_local_paths


def test_cleanup_s3_removes_old_objects(tmp_path: Path) -> None:
    settings = Settings(
        STORAGE_BACKEND="s3",
        LOCAL_STORAGE_DIR=str(tmp_path),
        S3_BUCKET="bucket",
        S3_REGION="us-east-1",
        RAW_RECORDING_RETENTION_DAYS=30,
        SUMMARY_RETENTION_DAYS=10,
        TRANSCRIPT_RETENTION_DAYS=15,
        STORAGE_CLEANUP_INTERVAL_HOURS=24,
    )

    client = boto3.client("s3", region_name="us-east-1")
    stubber = Stubber(client)

    now = datetime(2024, 1, 31, tzinfo=UTC)

    stubber.add_response(
        "list_objects_v2",
        {
            "Contents": [
                {"Key": "raw/2023/old.mp3", "LastModified": now - timedelta(days=40)},
                {"Key": "raw/2024/recent.mp3", "LastModified": now - timedelta(days=5)},
            ],
            "IsTruncated": False,
        },
        {"Bucket": "bucket", "Prefix": "raw/"},
    )
    stubber.add_response(
        "delete_object",
        {},
        {"Bucket": "bucket", "Key": "raw/2023/old.mp3"},
    )
    stubber.add_response(
        "list_objects_v2",
        {
            "Contents": [
                {"Key": "summaries/2023/old.md", "LastModified": now - timedelta(days=20)},
                {"Key": "summaries/2024/recent.md", "LastModified": now - timedelta(days=2)},
            ],
            "IsTruncated": False,
        },
        {"Bucket": "bucket", "Prefix": "summaries/"},
    )
    stubber.add_response(
        "delete_object",
        {},
        {"Bucket": "bucket", "Key": "summaries/2023/old.md"},
    )
    stubber.add_response(
        "list_objects_v2",
        {
            "Contents": [
                {"Key": "transcripts/2023/old.txt", "LastModified": now - timedelta(days=25)},
                {"Key": "transcripts/2024/recent.txt", "LastModified": now - timedelta(days=3)},
            ],
            "IsTruncated": False,
        },
        {"Bucket": "bucket", "Prefix": "transcripts/"},
    )
    stubber.add_response(
        "delete_object",
        {},
        {"Bucket": "bucket", "Key": "transcripts/2023/old.txt"},
    )

    with stubber:
        service = StorageService(settings=settings, s3_client=client)
        report = service.cleanup_expired_assets(now=now)

    assert sorted(report.removed_s3_keys) == [
        "raw/2023/old.mp3",
        "summaries/2023/old.md",
        "transcripts/2023/old.txt",
    ]


@pytest.mark.asyncio
async def test_storage_cleanup_runner_run_once_invokes_service(tmp_path: Path) -> None:
    settings = Settings(
        STORAGE_BACKEND="local",
        LOCAL_STORAGE_DIR=str(tmp_path),
        STORAGE_CLEANUP_INTERVAL_HOURS=24,
    )
    service = MagicMock(spec=StorageService)
    expected = CleanupReport(removed_local_paths=["foo"], removed_s3_keys=[])
    service.cleanup_expired_assets.return_value = expected

    runner = StorageCleanupRunner(storage_service=service, settings=settings)
    now = datetime.now(tz=UTC)

    report = await runner.run_once(now=now)

    service.cleanup_expired_assets.assert_called_once_with(now=now)
    assert report is expected


def test_storage_cleanup_runner_respects_fractional_interval(tmp_path: Path) -> None:
    settings = Settings(
        STORAGE_BACKEND="local",
        LOCAL_STORAGE_DIR=str(tmp_path),
        STORAGE_CLEANUP_INTERVAL_HOURS=0.05,
    )
    service = MagicMock(spec=StorageService)

    runner = StorageCleanupRunner(storage_service=service, settings=settings)

    assert runner.is_enabled
    assert runner.interval_seconds == max(1, int(0.05 * 3600))


@pytest.mark.asyncio
async def test_storage_cleanup_runner_can_be_disabled(tmp_path: Path) -> None:
    settings = Settings(
        STORAGE_BACKEND="local",
        LOCAL_STORAGE_DIR=str(tmp_path),
        STORAGE_CLEANUP_INTERVAL_HOURS=0,
    )
    service = MagicMock(spec=StorageService)

    runner = StorageCleanupRunner(storage_service=service, settings=settings)

    assert not runner.is_enabled
    assert runner.interval_seconds is None

    await runner.run_periodic()

    service.cleanup_expired_assets.assert_not_called()
