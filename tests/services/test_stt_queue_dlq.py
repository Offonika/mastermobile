from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import Column, Table, create_engine, event
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from apps.mw.src.db.models import (
    Base,
    CallDirection,
    CallExport,
    CallExportStatus,
    CallRecord,
    CallRecordStatus,
)
from apps.mw.src.services.stt_queue import STT_PROCESSED_KEY, DLQEntry, STTJob, STTQueue


class _FakeRedis:
    """Minimal in-memory Redis replacement used for queue tests."""

    def __init__(self) -> None:
        self._lists: defaultdict[str, list[str]] = defaultdict(list)
        self._sets: defaultdict[str, set[str]] = defaultdict(set)

    def rpush(self, key: str, value: str) -> int:
        self._lists[key].append(value)
        return len(self._lists[key])

    def lpop(self, key: str) -> str | None:
        values = self._lists.get(key)
        if not values:
            return None
        return values.pop(0)

    def blpop(self, keys: list[str], timeout: int = 0) -> tuple[str, str] | None:
        for key in keys:
            item = self.lpop(key)
            if item is not None:
                return key, item
        return None

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        values = list(self._lists.get(key, []))
        length = len(values)
        if length == 0:
            return []

        if start < 0:
            start = max(length + start, 0)
        if stop < 0:
            stop = length + stop
        stop = min(stop, length - 1)
        if start > stop:
            return []
        return values[start : stop + 1]

    def lrem(self, key: str, count: int, value: str) -> int:
        values = self._lists.get(key, [])
        if not values:
            return 0

        removed = 0
        if count == 0:
            new_values = [item for item in values if item != value]
            removed = len(values) - len(new_values)
            self._lists[key] = new_values
            return removed

        new_values: list[str] = []
        for item in values:
            if item == value and removed < count:
                removed += 1
                continue
            new_values.append(item)
        self._lists[key] = new_values
        return removed

    def sadd(self, key: str, value: str) -> int:
        before = len(self._sets[key])
        self._sets[key].add(value)
        return int(len(self._sets[key]) > before)

    def sismember(self, key: str, value: str) -> bool:
        return value in self._sets[key]

    def srem(self, key: str, value: str) -> int:
        if value in self._sets[key]:
            self._sets[key].remove(value)
            return 1
        return 0


def _sqlite_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover - sqlite hook
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def _ensure_core_users_table() -> Table:
    if "core.users" in Base.metadata.tables:
        return Base.metadata.tables["core.users"]
    return Table(
        "core.users",
        Base.metadata,
        Column("user_id", PGUUID(as_uuid=True), primary_key=True),
    )


def test_requeue_dlq_entry_resets_state_and_requeues_job() -> None:
    engine = _sqlite_engine()
    core_users = _ensure_core_users_table()
    Base.metadata.create_all(
        engine,
        tables=[core_users, CallExport.__table__, CallRecord.__table__],
    )

    redis = _FakeRedis()
    queue = STTQueue(redis)

    now = datetime.now(datetime.UTC)
    with Session(engine) as session:
        export = CallExport(
            period_from=now,
            period_to=now,
            status=CallExportStatus.PENDING,
            options=None,
        )
        record = CallRecord(
            export=export,
            call_id="CALL-123",
            direction=CallDirection.INBOUND,
            from_number="123",
            to_number="456",
            duration_sec=60,
            status=CallRecordStatus.ERROR,
            recording_url="https://example.com/call.wav",
            error_code="stt_failed",
            error_message="timeout",
        )
        session.add_all([export, record])
        session.commit()
        record_id = record.id

    job = STTJob(
        record_id=record_id,
        call_id="CALL-123",
        recording_url="https://example.com/call.wav",
        engine="whisper",  # pragma: allowlist secret
        language="ru",
    )
    queue.mark_processed(job)
    dlq_entry = DLQEntry(job=job, reason="transcription failed", status_code=500)
    queue.push_to_dlq(dlq_entry)

    entries = queue.list_dlq_entries()
    assert len(entries) == 1
    entry_id = entries[0].entry_id

    with Session(engine) as session:
        restored_entry = queue.requeue_dlq_entry(session, entry_id)
        assert restored_entry is not None
        assert restored_entry.reason == "transcription failed"

        record = session.get(CallRecord, record_id)
        assert record is not None
        assert record.status is CallRecordStatus.DOWNLOADED
        assert record.error_code is None
        assert record.error_message is None

    assert queue.list_dlq_entries() == []
    assert not redis.sismember(STT_PROCESSED_KEY, job.dedup_key)

    fetched = queue.fetch_job(timeout=0)
    assert fetched == job
    assert queue.fetch_job(timeout=0) is None

    engine.dispose()
