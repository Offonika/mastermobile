from __future__ import annotations

import codecs
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import Column, Table, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from apps.mw.src.app import app
from apps.mw.src.db.models import (
    Base,
    CallDirection,
    CallExport,
    CallExportStatus,
    CallRecord,
    CallRecordStatus,
)
from apps.mw.src.db.session import configure_engine, engine as default_engine, get_session

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
            run_id="00000000-0000-0000-0000-000000000001",
            period_from=period_from,
            period_to=period_to,
            status=CallExportStatus.COMPLETED,
        )
        in_range = CallRecord(
            export=export,
            call_id="CALL-001",
            record_id="REC-001",
            started_at=datetime(2024, 1, 1, 10, 30, 0),
            direction=CallDirection.INBOUND,
            employee_id="EMP-001",
            from_number="+700000001",
            to_number="+700000002",
            duration_sec=180,
            recording_url="https://example.com/records/1.mp3",
            transcript_path="transcripts/call_001.txt",
            text_preview="Customer asked about pricing.",
            transcription_cost=Decimal("18.00"),
            currency_code="RUB",
            language="ru",
            status=CallRecordStatus.COMPLETED,
            checksum="abc123",
            summary_path="summary/call_001.md",
        )
        out_of_range = CallRecord(
            export=export,
            call_id="CALL-002",
            record_id="REC-002",
            started_at=datetime(2024, 1, 2, 12, 0, 0),
            direction=CallDirection.OUTBOUND,
            employee_id="EMP-002",
            from_number="+700000003",
            to_number="+700000004",
            duration_sec=60,
            recording_url="https://example.com/records/2.mp3",
            transcript_path="transcripts/call_002.txt",
            transcription_cost=Decimal("9.50"),
            currency_code="RUB",
            language="ru",
            status=CallRecordStatus.COMPLETED,
        )
        session.add_all([export, in_range, out_of_range])
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

    assert chunks
    content = b"".join(chunks)
    assert content.startswith(codecs.BOM_UTF8)
    decoded = content.decode("utf-8-sig")
    lines = [line for line in decoded.splitlines() if line]
    assert lines[0] == (
        "run_id;call_id;record_id;datetime_start;direction;employee;from;to;duration_sec;"
        "recording_url;transcript_path;text_preview;transcription_cost;currency_code;language;"
        "status;error_code;retry_count;checksum;summary_path"
    )
    assert lines[1] == (
        "00000000-0000-0000-0000-000000000001;CALL-001;REC-001;2024-01-01T10:30:00;"
        "inbound;EMP-001;+700000001;+700000002;180;https://example.com/records/1.mp3;"
        "transcripts/call_001.txt;Customer asked about pricing.;18.00;RUB;ru;completed;;0;"
        "abc123;summary/call_001.md"
    )
    assert len(lines) == 2


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
async def test_export_call_registry_returns_json(
    api_client: httpx.AsyncClient,
    sqlite_engine: Engine,
) -> None:
    _seed_call_records(sqlite_engine)

    response = await api_client.get(
        "/api/v1/call-registry/json",
        params={
            "period_from": "2024-01-01T00:00:00",
            "period_to": "2024-01-01T23:59:59",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == [
        {
            "run_id": "00000000-0000-0000-0000-000000000001",
            "call_id": "CALL-001",
            "record_id": "REC-001",
            "datetime_start": "2024-01-01T10:30:00",
            "direction": "inbound",
            "employee": "EMP-001",
            "from": "+700000001",
            "to": "+700000002",
            "duration_sec": 180,
            "recording_url": "https://example.com/records/1.mp3",
            "transcript_path": "transcripts/call_001.txt",
            "text_preview": "Customer asked about pricing.",
            "transcription_cost": "18.00",
            "currency_code": "RUB",
            "language": "ru",
            "status": "completed",
            "error_code": None,
            "retry_count": 0,
            "checksum": "abc123",
            "summary_path": "summary/call_001.md",
        }
    ]
