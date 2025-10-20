from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Table, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from apps.mw.src.db import Base
from apps.mw.src.db.models import (
    B24Transcript,
    CallDirection,
    CallExport,
    CallExportStatus,
    CallRecord,
    CallRecordStatus,
)


@contextmanager
def transcript_session() -> Iterator[Session]:
    """Provide an in-memory SQLite session with transcript tables."""

    engine = _build_engine()
    SessionLocal = sessionmaker(bind=engine, future=True)
    try:
        with SessionLocal() as session:
            yield session
    finally:
        engine.dispose()


def _build_engine() -> Engine:
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
    Base.metadata.create_all(
        engine,
        tables=[CallExport.__table__, CallRecord.__table__, B24Transcript.__table__],
    )
    return engine


def make_call_record(session: Session, call_id: str = "CALL-001") -> CallRecord:
    """Insert a call export and associated record for testing."""

    export = CallExport(
        run_id=uuid4(),
        period_from=datetime(2024, 1, 1, tzinfo=datetime.UTC),
        period_to=datetime(2024, 1, 2, tzinfo=datetime.UTC),
        status=CallExportStatus.PENDING,
    )
    record = CallRecord(
        export=export,
        call_id=call_id,
        record_id=f"{call_id}-rec",
        call_started_at=datetime(2024, 1, 1, 12, 0, tzinfo=datetime.UTC),
        direction=CallDirection.INBOUND,
        from_number="+79990000001",
        to_number="+79990000002",
        duration_sec=180,
        recording_url=f"https://example.com/records/{call_id}.mp3",
        status=CallRecordStatus.COMPLETED,
    )
    session.add_all([export, record])
    session.commit()
    session.refresh(record)
    return record
