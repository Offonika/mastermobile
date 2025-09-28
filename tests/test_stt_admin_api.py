from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

import pytest
from fastapi import status
from loguru import logger
from sqlalchemy import Column, Table, create_engine, event
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from apps.mw.src.api.dependencies import Principal, ProblemDetailException, require_admin
from apps.mw.src.api.routes.stt_admin import requeue_stt_dlq_entry
from apps.mw.src.db.models import (
    Base,
    CallDirection,
    CallExport,
    CallExportStatus,
    CallRecord,
    CallRecordStatus,
)
from apps.mw.src.services.stt_queue import DLQEntry, STTJob, STTQueue


class _FakeRedis:
    """Minimal in-memory Redis replacement used for admin API tests."""

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
        new_values: list[str] = []
        for item in values:
            if item == value and (count == 0 or removed < count):
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


@pytest.mark.parametrize(
    "roles,expected_status",
    [
        (frozenset({"admin"}), None),
        (frozenset(), status.HTTP_403_FORBIDDEN),
    ],
)
def test_require_admin_role_check(roles: frozenset[str], expected_status: int | None) -> None:
    principal = Principal(subject="user-1", roles=roles, request_id="req-1")

    if expected_status is None:
        assert require_admin(principal) is principal
    else:
        with pytest.raises(ProblemDetailException) as exc:
            require_admin(principal)
        assert exc.value.error.status == expected_status


def test_admin_requeue_records_audit_event() -> None:
    engine = _sqlite_engine()
    core_users = _ensure_core_users_table()
    Base.metadata.create_all(
        engine,
        tables=[core_users, CallExport.__table__, CallRecord.__table__],
    )

    redis = _FakeRedis()
    queue = STTQueue(redis)

    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        export = CallExport(
            period_from=now,
            period_to=now,
            status=CallExportStatus.PENDING,
            options=None,
        )
        record = CallRecord(
            export=export,
            call_id="CALL-42",
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
        call_id="CALL-42",
        recording_url="https://example.com/call.wav",
        engine="whisper",
        language="ru",
    )
    queue.mark_processed(job)
    dlq_entry = DLQEntry(job=job, reason="transcription failed", status_code=500)
    queue.push_to_dlq(dlq_entry)
    entry_id = queue.list_dlq_entries()[0].entry_id

    principal = Principal(subject="admin-1", roles=frozenset({"admin"}), request_id="req-123")

    captured: list[str] = []
    sink_id = logger.add(captured.append, level="INFO", serialize=True)
    try:
        with Session(engine) as session:
            response = requeue_stt_dlq_entry(
                entry_id,
                session=session,
                queue=queue,
                admin=principal,
            )

        assert response.status == "requeued"
        assert response.entry_id == entry_id
        assert response.job.record_id == record_id
    finally:
        logger.remove(sink_id)
        engine.dispose()

    assert captured, "expected audit log entry"
    payload = json.loads(captured[0])
    record = payload["record"]
    extra = record["extra"]
    assert extra["audit"] is True
    assert extra["event"] == "stt_dlq_requeue"
    assert extra["who"] == "admin-1"
    assert extra["entry_id"] == entry_id
    assert extra["why"] == "manual_requeue"
    assert record["message"] == "Admin requeued STT DLQ entry"
