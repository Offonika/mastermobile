"""Integration tests for call export and call record ORM models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Column, Table, create_engine, event, insert, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.mw.src.db.models import (
    Base,
    CallExport,
    CallExportStatus,
    CallDirection,
    CallRecord,
    CallRecordStatus,
)


def _ensure_core_users_table() -> Table:
    if "core.users" not in Base.metadata.tables:
        return Table(
            "core.users",
            Base.metadata,
            Column("user_id", PGUUID(as_uuid=True), primary_key=True),
        )
    return Base.metadata.tables["core.users"]


def _sqlite_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover - event hook
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def test_call_export_crud_matches_schema() -> None:
    """Persist, update and delete a call export run."""

    engine = _sqlite_engine()
    core_users = _ensure_core_users_table()
    Base.metadata.create_all(
        engine,
        tables=[core_users, CallExport.__table__, CallRecord.__table__],
    )

    actor_id = uuid4()
    with engine.begin() as conn:
        conn.execute(insert(core_users).values(user_id=actor_id))

    period_from = datetime(2024, 9, 1, tzinfo=timezone.utc)
    period_to = period_from + timedelta(days=1)

    with Session(engine) as session:
        export = CallExport(
            period_from=period_from,
            period_to=period_to,
            status=CallExportStatus.PENDING,
            actor_user_id=actor_id,
            options={"generate_summary": True},
        )
        session.add(export)
        session.commit()
        run_id: UUID = export.run_id
        session.expunge_all()

        loaded = session.get(CallExport, run_id)
        assert loaded is not None
        assert loaded.status is CallExportStatus.PENDING
        assert loaded.period_from == period_from.replace(tzinfo=None)
        assert loaded.period_to == period_to.replace(tzinfo=None)
        assert loaded.actor_user_id == actor_id
        assert loaded.options == {"generate_summary": True}

        finished_at = period_to + timedelta(hours=1)
        loaded.status = CallExportStatus.COMPLETED
        loaded.finished_at = finished_at
        session.commit()
        session.expunge_all()

        refreshed = session.get(CallExport, run_id)
        assert refreshed is not None
        assert refreshed.status is CallExportStatus.COMPLETED
        assert refreshed.finished_at == finished_at.replace(tzinfo=None)

        session.delete(refreshed)
        session.commit()
        assert session.get(CallExport, run_id) is None

    engine.dispose()


def test_call_record_crud_and_cascade() -> None:
    """Ensure call records match schema constraints and cascade with exports."""

    engine = _sqlite_engine()
    core_users = _ensure_core_users_table()
    Base.metadata.create_all(
        engine,
        tables=[core_users, CallExport.__table__, CallRecord.__table__],
    )

    period_from = datetime(2024, 9, 1, tzinfo=timezone.utc)
    period_to = period_from + timedelta(days=1)

    with Session(engine) as session:
        export = CallExport(
            period_from=period_from,
            period_to=period_to,
            status=CallExportStatus.PENDING,
            options=None,
        )
        record = CallRecord(
            export=export,
            call_id="CALL-001",
            direction=CallDirection.INBOUND,
            from_number="+74951234567",
            to_number="+79997654321",
            duration_sec=180,
            status=CallRecordStatus.PENDING,
            transcript_lang="ru",
        )
        session.add_all([export, record])
        session.commit()
        run_id = export.run_id
        record_id = record.id
        session.expunge_all()

        loaded = session.scalars(
            select(CallRecord).where(CallRecord.id == record_id)
        ).one()
        assert loaded.run_id == run_id
        assert loaded.call_id == "CALL-001"
        assert loaded.direction is CallDirection.INBOUND
        assert loaded.from_number == "+74951234567"
        assert loaded.to_number == "+79997654321"
        assert loaded.record_id is None
        assert loaded.duration_sec == 180
        assert loaded.status is CallRecordStatus.PENDING
        assert loaded.transcript_lang == "ru"
        assert loaded.cost_currency == "RUB"

        last_attempt = period_to + timedelta(hours=2)
        loaded.status = CallRecordStatus.COMPLETED
        loaded.attempts = 1
        loaded.last_attempt_at = last_attempt
        loaded.storage_path = "/storage/call-001.wav"
        loaded.checksum = "abc123"
        loaded.cost_amount = Decimal("12.34")
        loaded.direction = CallDirection.OUTBOUND
        loaded.from_number = "+74959876543"
        loaded.to_number = "+78005553535"
        session.commit()
        session.expunge_all()

        updated = session.get(CallRecord, record_id)
        assert updated is not None
        assert updated.status is CallRecordStatus.COMPLETED
        assert updated.attempts == 1
        assert updated.last_attempt_at == last_attempt.replace(tzinfo=None)
        assert updated.storage_path == "/storage/call-001.wav"
        assert updated.checksum == "abc123"
        assert updated.cost_amount == Decimal("12.34")
        assert updated.cost_currency == "RUB"
        assert updated.direction is CallDirection.OUTBOUND
        assert updated.from_number == "+74959876543"
        assert updated.to_number == "+78005553535"

        updated.status = CallRecordStatus.MISSING_AUDIO
        updated.error_code = "http_404"
        updated.error_message = "Recording was not found"
        updated.attempts = 5
        session.commit()
        session.expunge_all()

        missing = session.get(CallRecord, record_id)
        assert missing is not None
        assert missing.status is CallRecordStatus.MISSING_AUDIO
        assert missing.error_code == "http_404"
        assert missing.error_message == "Recording was not found"
        assert missing.attempts == 5

        duplicate = CallRecord(
            run_id=run_id,
            call_id="CALL-001",
            direction=CallDirection.OUTBOUND,
            from_number="+74951230000",
            to_number="+78001230000",
            duration_sec=60,
            status=CallRecordStatus.PENDING,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        export_obj = session.get(CallExport, run_id)
        assert export_obj is not None
        session.delete(export_obj)
        session.commit()
        assert session.get(CallRecord, record_id) is None

    engine.dispose()
