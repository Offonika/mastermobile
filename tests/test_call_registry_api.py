from __future__ import annotations

import codecs
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import Column, Table, create_engine
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import httpx
import pytest_asyncio
from apps.mw.src.app import app
from apps.mw.src.db.models import (
    Base,
    CallExport,
    CallExportStatus,
    CallRecord,
    CallRecordStatus,
)
from apps.mw.src.db.session import configure_engine, get_session
from apps.mw.src.db.session import engine as default_engine

BASE_URL = "http://testserver"


def _ensure_core_users_table() -> Table:
    if "core.users" not in Base.metadata.tables:
        return Table(
            "core.users",
            Base.metadata,
            Column("user_id", PGUUID(as_uuid=True), primary_key=True),
        )
    return Base.metadata.tables["core.users"]


@pytest.fixture()
def sqlite_engine() -> Engine:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    core_users = _ensure_core_users_table()
    Base.metadata.create_all(
        engine,
        tables=[core_users, CallExport.__table__, CallRecord.__table__],
    )
    configure_engine(engine)
    yield engine
    configure_engine(default_engine)
    engine.dispose()


@pytest_asyncio.fixture()
async def api_client(sqlite_engine: Engine) -> httpx.AsyncClient:
    def override_get_session() -> Session:
        session = Session(bind=sqlite_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


def _seed_call_records(engine: Engine) -> None:
    period_from = datetime(2024, 1, 1, 0, 0, 0)
    period_to = period_from + timedelta(days=1)

    with Session(engine) as session:
        export = CallExport(
            period_from=period_from,
            period_to=period_to,
            status=CallExportStatus.COMPLETED,
        )
        in_range = CallRecord(
            export=export,
            call_id="CALL-001",
            record_id="REC-001",
            call_started_at=datetime(2024, 1, 1, 10, 30, 0),
            direction="inbound",
            from_number="+700000001",
            to_number="+700000002",
            duration_sec=180,
            recording_url="https://example.com/records/1.mp3",
            status=CallRecordStatus.COMPLETED,
            employee_id="EMP-001",
            transcript_path="transcripts/call_001.txt",
            summary_path="summary/call_001.md",
            text_preview="Позвонил клиент, уточнил статус заказа",
            transcription_cost=Decimal("18.00"),
            currency_code="RUB",
            language="ru",
            checksum="abc123",
        )
        out_of_range = CallRecord(
            export=export,
            call_id="CALL-002",
            record_id="REC-002",
            call_started_at=datetime(2024, 1, 2, 12, 0, 0),
            direction="outbound",
            from_number="+700000003",
            to_number="+700000004",
            duration_sec=60,
            recording_url="https://example.com/records/2.mp3",
            status=CallRecordStatus.COMPLETED,
            employee_id="EMP-002",
            transcription_cost=Decimal("6.00"),
            currency_code="RUB",
        )
        session.add_all([export, in_range, out_of_range])
        session.commit()


def _seed_b24_call_records(engine: Engine) -> None:
    with Session(engine) as session:
        export = CallExport(
            period_from=datetime(2024, 2, 1, 0, 0, 0),
            period_to=datetime(2024, 2, 2, 0, 0, 0),
            status=CallExportStatus.COMPLETED,
        )
        with_transcript = CallRecord(
            export=export,
            call_id="CALL-100",
            record_id="REC-100",
            call_started_at=datetime(2024, 2, 1, 9, 0, 0),
            direction="inbound",
            from_number="+701000001",
            to_number="+701000002",
            duration_sec=240,
            recording_url="https://example.com/records/100.mp3",
            transcript_path="s3://bucket/call_100.txt",
            summary_path="summary/call_100.md",
            text_preview="Клиент благодарит за консультацию",
            language="ru",
            transcription_cost=Decimal("24.00"),
            currency_code="RUB",
            status=CallRecordStatus.COMPLETED,
            employee_id="EMP-900",
            checksum="checksum-100",
        )
        without_transcript = CallRecord(
            export=export,
            call_id="CALL-200",
            record_id="REC-200",
            call_started_at=datetime(2024, 2, 1, 12, 0, 0),
            direction="outbound",
            from_number="+701000003",
            to_number="+701000004",
            duration_sec=180,
            recording_url="https://example.com/records/200.mp3",
            transcript_path=None,
            status=CallRecordStatus.COMPLETED,
            employee_id="EMP-901",
            transcription_cost=Decimal("12.00"),
            currency_code="RUB",
            language="en",
        )
        outside_range = CallRecord(
            export=export,
            call_id="CALL-300",
            record_id="REC-300",
            call_started_at=datetime(2024, 1, 25, 10, 0, 0),
            direction="inbound",
            from_number="+701000005",
            to_number="+701000006",
            duration_sec=120,
            recording_url="https://example.com/records/300.mp3",
            transcript_path="",
            status=CallRecordStatus.COMPLETED,
            employee_id="EMP-900",
            transcription_cost=Decimal("6.00"),
            currency_code="RUB",
        )
        session.add_all([export, with_transcript, without_transcript, outside_range])
        session.commit()


def test_call_record_duplicate_recording_url_is_rejected(sqlite_engine: Engine) -> None:
    first_period_from = datetime(2024, 3, 1, 0, 0, 0)
    first_period_to = first_period_from + timedelta(days=1)

    with Session(sqlite_engine) as session:
        first_export = CallExport(
            period_from=first_period_from,
            period_to=first_period_to,
            status=CallExportStatus.COMPLETED,
        )
        original_record = CallRecord(
            export=first_export,
            call_id="CALL-DEDUP",
            record_id="REC-ORIGINAL",
            call_started_at=datetime(2024, 3, 1, 9, 0, 0),
            direction="inbound",
            from_number="+702000001",
            to_number="+702000002",
            duration_sec=120,
            recording_url="https://example.com/records/dedup.mp3",
            status=CallRecordStatus.COMPLETED,
            employee_id="EMP-DEDUP",
        )
        session.add_all([first_export, original_record])
        session.commit()

    second_period_from = datetime(2024, 3, 2, 0, 0, 0)
    second_period_to = second_period_from + timedelta(days=1)

    with Session(sqlite_engine) as session:
        second_export = CallExport(
            period_from=second_period_from,
            period_to=second_period_to,
            status=CallExportStatus.COMPLETED,
        )
        conflicting_record = CallRecord(
            export=second_export,
            call_id="CALL-DEDUP",
            record_id="REC-SECOND",
            call_started_at=datetime(2024, 3, 2, 11, 0, 0),
            direction="outbound",
            from_number="+702000003",
            to_number="+702000004",
            duration_sec=60,
            recording_url="https://example.com/records/dedup.mp3",
            status=CallRecordStatus.COMPLETED,
            employee_id="EMP-DED2",
        )
        session.add_all([second_export, conflicting_record])

        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.asyncio
async def test_export_call_registry_streams_csv(
    api_client: httpx.AsyncClient,
    sqlite_engine: Engine,
) -> None:
    _seed_call_records(sqlite_engine)

    async with api_client.stream(
        "GET",
        "/api/v1/call-registry",
        params={
            "period_from": "2024-01-01T00:00:00",
            "period_to": "2024-01-01T23:59:59",
        },
        headers={"X-Request-Id": "req-call-registry-1"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("text/csv")
        assert response.headers["X-Request-Id"] == "req-call-registry-1"
        expected_filename = (
            "registry/calls_20240101T000000_20240101T235959.csv"
        )
        assert response.headers["Content-Disposition"] == (
            f'attachment; filename="{expected_filename}"'
        )

        chunks = [chunk async for chunk in response.aiter_bytes()]

    assert len(chunks) >= 1
    content = b"".join(chunks)
    assert content.startswith(codecs.BOM_UTF8)
    decoded = content.decode("utf-8-sig")
    lines = [line for line in decoded.splitlines() if line]
    expected_headers = [
        "run_id",
        "call_id",
        "record_id",
        "employee",
        "datetime_start",
        "direction",
        "from",
        "to",
        "duration_sec",
        "recording_url",
        "transcript_path",
        "summary_path",
        "text_preview",
        "transcription_cost",
        "currency_code",
        "language",
        "status",
        "error_code",
        "retry_count",
        "checksum",
    ]
    header = lines[0].split(";")
    assert header == expected_headers
    assert len(lines) == 2
    values = lines[1].split(";")
    row = dict(zip(header, values, strict=False))
    assert row["call_id"] == "CALL-001"
    assert row["record_id"] == "REC-001"
    assert row["employee"] == "EMP-001"
    assert row["datetime_start"] == "2024-01-01T10:30:00"
    assert row["direction"] == "inbound"
    assert row["from"] == "+700000001"
    assert row["to"] == "+700000002"
    assert row["duration_sec"] == "180"
    assert row["recording_url"] == "https://example.com/records/1.mp3"
    assert row["transcript_path"] == "transcripts/call_001.txt"
    assert row["summary_path"] == "summary/call_001.md"
    assert row["text_preview"] == "Позвонил клиент, уточнил статус заказа"
    assert row["transcription_cost"] == "18.00"
    assert row["currency_code"] == "RUB"
    assert row["language"] == "ru"
    assert row["status"] == "completed"
    assert row["error_code"] == ""
    assert row["retry_count"] == "0"
    assert row["checksum"] == "abc123"


@pytest.mark.asyncio
async def test_export_call_registry_validates_period(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(
        "/api/v1/call-registry",
        params={
            "period_from": "2024-01-02T00:00:00",
            "period_to": "2024-01-01T00:00:00",
        },
        headers={"X-Request-Id": "req-call-registry-2"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["title"] == "Invalid period range"
    assert payload["status"] == 400


@pytest.mark.asyncio
async def test_export_b24_calls_csv_applies_filters(
    api_client: httpx.AsyncClient,
    sqlite_engine: Engine,
) -> None:
    _seed_b24_call_records(sqlite_engine)

    async with api_client.stream(
        "GET",
        "/api/v1/b24-calls/export.csv",
        params={
            "employee_id": "EMP-900",
            "date_from": "2024-02-01T00:00:00",
            "date_to": "2024-02-01T23:59:59",
            "has_text": "true",
        },
        headers={"X-Request-Id": "req-b24-csv"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["X-Request-Id"] == "req-b24-csv"
        assert response.headers["Content-Type"].startswith("text/csv")
        assert response.headers["Content-Disposition"] == (
            'attachment; filename="b24_calls_20240201T000000_20240201T235959.csv"'
        )
        chunks = [chunk async for chunk in response.aiter_bytes()]

    content = b"".join(chunks)
    assert content.startswith(codecs.BOM_UTF8)
    decoded = content.decode("utf-8-sig")
    rows = [line for line in decoded.splitlines() if line]
    expected_headers = [
        "run_id",
        "call_id",
        "record_id",
        "employee",
        "datetime_start",
        "direction",
        "from",
        "to",
        "duration_sec",
        "recording_url",
        "transcript_path",
        "summary_path",
        "text_preview",
        "transcription_cost",
        "currency_code",
        "language",
        "status",
        "error_code",
        "retry_count",
        "checksum",
        "has_text",
    ]
    header = rows[0].split(";")
    assert header == expected_headers
    assert len(rows) == 2
    values = rows[1].split(";")
    row = dict(zip(header, values, strict=False))
    assert row["call_id"] == "CALL-100"
    assert row["record_id"] == "REC-100"
    assert row["employee"] == "EMP-900"
    assert row["datetime_start"] == "2024-02-01T09:00:00"
    assert row["direction"] == "inbound"
    assert row["from"] == "+701000001"
    assert row["to"] == "+701000002"
    assert row["duration_sec"] == "240"
    assert row["recording_url"] == "https://example.com/records/100.mp3"
    assert row["transcript_path"] == "s3://bucket/call_100.txt"
    assert row["summary_path"] == "summary/call_100.md"
    assert row["text_preview"] == "Клиент благодарит за консультацию"
    assert row["transcription_cost"] == "24.00"
    assert row["currency_code"] == "RUB"
    assert row["language"] == "ru"
    assert row["status"] == "completed"
    assert row["error_code"] == ""
    assert row["retry_count"] == "0"
    assert row["checksum"] == "checksum-100"
    assert row["has_text"] == "true"


@pytest.mark.asyncio
async def test_export_b24_calls_json_filters_and_returns_payload(
    api_client: httpx.AsyncClient,
    sqlite_engine: Engine,
) -> None:
    _seed_b24_call_records(sqlite_engine)

    response = await api_client.get(
        "/api/v1/b24-calls/export.json",
        params={
            "employee_id": "EMP-901",
            "date_from": "2024-02-01T00:00:00",
            "date_to": "2024-02-01T23:59:59",
            "has_text": "false",
        },
        headers={"X-Request-Id": "req-b24-json"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "req-b24-json"
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    record = payload[0]
    assert record["call_id"] == "CALL-200"
    assert record["employee"] == "EMP-901"
    assert record["has_text"] is False
    assert record["transcript_path"] is None
    assert record["text_preview"] is None
    assert record["language"] == "en"
    assert record["transcription_cost"] == "12.00"
    assert record["currency_code"] == "RUB"
    assert record["retry_count"] == 0


@pytest.mark.asyncio
async def test_export_b24_calls_validates_period(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(
        "/api/v1/b24-calls/export.json",
        params={
            "date_from": "2024-02-02T00:00:00",
            "date_to": "2024-02-01T00:00:00",
        },
        headers={"X-Request-Id": "req-b24-invalid"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["title"] == "Invalid date range"
    assert body["status"] == 400


def _make_export(session: Session) -> CallExport:
    export = CallExport(
        period_from=datetime(2024, 3, 1, 0, 0, 0),
        period_to=datetime(2024, 3, 2, 0, 0, 0),
        status=CallExportStatus.PENDING,
    )
    session.add(export)
    session.flush()
    return export


def _base_call_record_kwargs() -> dict[str, object]:
    return {
        "call_id": "CALL-INVALID",
        "record_id": "REC-INVALID",
        "duration_sec": 10,
        "status": CallRecordStatus.PENDING,
    }


def test_call_record_rejects_invalid_direction(sqlite_engine: Engine) -> None:
    with Session(sqlite_engine) as session:
        export = _make_export(session)
        record = CallRecord(
            export=export,
            direction="sideways",
            from_number="+79999999999",
            to_number="+79999999998",
            **_base_call_record_kwargs(),
        )
        session.add(record)

        with pytest.raises(StatementError):
            session.flush()
        session.rollback()


def test_call_record_rejects_null_numbers(sqlite_engine: Engine) -> None:
    with Session(sqlite_engine) as session:
        export = _make_export(session)
        null_from = CallRecord(
            export=export,
            direction="inbound",
            from_number=None,
            to_number="+78888888888",
            **_base_call_record_kwargs(),
        )
        session.add(null_from)

        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_call_record_rejects_blank_numbers(sqlite_engine: Engine) -> None:
    with Session(sqlite_engine) as session:
        export = _make_export(session)
        blank_to = CallRecord(
            export=export,
            direction="inbound",
            from_number="+78888888888",
            to_number="   ",
            **_base_call_record_kwargs(),
        )
        session.add(blank_to)

        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
