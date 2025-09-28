from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from sqlalchemy import Column, String, Table, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from apps.mw.src.config import Settings
from apps.mw.src.db import Base
from apps.mw.src.db.models import (
    CallDirection,
    CallExport,
    CallExportStatus,
    CallRecord,
    CallRecordStatus,
)
from apps.mw.src.services.storage import StorageService
from apps.mw.src.services.summarizer import CallSummarizer
from apps.mw.src.services.stt_queue import STTJob, STTQueue
from apps.mw.src.services.stt_providers import TranscriptionResult
from apps.mw.src.services.stt_worker import STTWorker


class _DummyRedis:
    def __init__(self) -> None:
        self._sets: dict[str, set[str]] = {}

    def sadd(self, key: str, value: str) -> None:
        self._sets.setdefault(key, set()).add(value)

    def sismember(self, key: str, value: str) -> bool:
        return value in self._sets.get(key, set())


class _InMemoryQueue(STTQueue):
    def __init__(self, job: STTJob) -> None:
        super().__init__(_DummyRedis())
        self._jobs: list[STTJob] = [job]

    def fetch_job(self, *, timeout: int | None = None) -> STTJob | None:  # noqa: ARG002 - interface requirement
        if self._jobs:
            return self._jobs.pop(0)
        return None


class _StubTranscriber:
    def __init__(self, result: TranscriptionResult) -> None:
        self._result = result

    def transcribe(self, job: STTJob) -> TranscriptionResult:  # noqa: ARG002 - interface requirement
        return self._result


@contextmanager
def _prepare_engine() -> Iterator[Engine]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    if "core.users" not in Base.metadata.tables:
        Table(
            "users",
            Base.metadata,
            Column("user_id", String, primary_key=True),
            schema="core",
            extend_existing=True,
        )
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE IF NOT EXISTS "core.users" (user_id TEXT PRIMARY KEY)'))
    Base.metadata.create_all(engine, tables=[CallExport.__table__, CallRecord.__table__])
    try:
        yield engine
    finally:
        engine.dispose()


def _seed_record(session: Session) -> CallRecord:
    export = CallExport(
        run_id=uuid4(),
        period_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        period_to=datetime(2024, 1, 2, tzinfo=timezone.utc),
        status=CallExportStatus.IN_PROGRESS,
    )
    record = CallRecord(
        export=export,
        call_id="CALL-123",
        record_id="REC-123",
        call_started_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        direction=CallDirection.INBOUND,
        from_number="+70000000001",
        to_number="+70000000002",
        duration_sec=120,
        recording_url="https://example.com/records/call-123.mp3",
        status=CallRecordStatus.DOWNLOADED,
    )
    session.add(export)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def test_stt_worker_persists_summary_when_enabled(tmp_path: Path) -> None:
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    transcript_path = transcript_dir / "CALL-123.txt"
    transcript_path.write_text(
        "Менеджер приветствует клиента. Клиент уточняет статус заказа."
        " Менеджер обещает перезвонить. Сделка остаётся в работе.",
        encoding="utf-8",
    )

    with _prepare_engine() as engine:
        SessionFactory = sessionmaker(bind=engine, future=True)
        with SessionFactory() as session:
            record = _seed_record(session)

        settings = Settings(
            CALL_SUMMARY_ENABLED=True,
            LOCAL_STORAGE_DIR=str(tmp_path / "storage"),
        )
        storage = StorageService(settings=settings)
        summarizer = CallSummarizer(
            settings=settings,
            storage_service=storage,
            timestamp_provider=lambda: datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        )

        job = STTJob(
            record_id=record.id,
            call_id=record.call_id,
            recording_url=record.recording_url or "",
            engine="placeholder",
            language="ru",
        )
        queue = _InMemoryQueue(job)
        worker = STTWorker(
            queue,
            _StubTranscriber(TranscriptionResult(transcript_path=str(transcript_path), language="ru")),
            session_factory=SessionFactory,
            settings=settings,
            summarizer=summarizer,
        )

        assert worker.process_next() is True

        with SessionFactory() as verify_session:
            stored = verify_session.get(CallRecord, record.id)
            assert stored is not None
            assert stored.summary_path is not None
            summary_file = Path(stored.summary_path)
            assert summary_file.exists()
            lines = [line for line in summary_file.read_text(encoding="utf-8").splitlines() if line]
            assert 3 <= len(lines) <= 5
            assert all(line.startswith("- ") for line in lines)


def test_stt_worker_skips_summary_when_disabled(tmp_path: Path) -> None:
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    transcript_path = transcript_dir / "CALL-456.txt"
    transcript_path.write_text(
        "Клиент отменяет заказ. Менеджер подтверждает отмену.",
        encoding="utf-8",
    )

    with _prepare_engine() as engine:
        SessionFactory = sessionmaker(bind=engine, future=True)
        with SessionFactory() as session:
            record = _seed_record(session)

        settings = Settings(
            CALL_SUMMARY_ENABLED=False,
            LOCAL_STORAGE_DIR=str(tmp_path / "storage"),
        )
        storage = StorageService(settings=settings)
        summarizer = CallSummarizer(
            settings=settings,
            storage_service=storage,
            timestamp_provider=lambda: datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        )

        job = STTJob(
            record_id=record.id,
            call_id=record.call_id,
            recording_url=record.recording_url or "",
            engine="placeholder",
            language="ru",
        )
        queue = _InMemoryQueue(job)
        worker = STTWorker(
            queue,
            _StubTranscriber(TranscriptionResult(transcript_path=str(transcript_path), language="ru")),
            session_factory=SessionFactory,
            settings=settings,
            summarizer=summarizer,
        )

        assert worker.process_next() is True

        with SessionFactory() as verify_session:
            stored = verify_session.get(CallRecord, record.id)
            assert stored is not None
            assert stored.summary_path is None
        storage_root = Path(settings.local_storage_dir)
        assert not any(storage_root.rglob("*.md"))
