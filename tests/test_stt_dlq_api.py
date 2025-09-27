"""Tests for the STT DLQ replay administrative endpoint."""
from __future__ import annotations

from typing import AsyncIterator, Iterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.mw.src.app import app
from apps.mw.src.api.routes.stt import get_stt_queue
from apps.mw.src.config import get_settings
from apps.mw.src.db.models import AuditLog
from apps.mw.src.db.session import configure_engine, engine as default_engine, get_session
from apps.mw.src.services.stt_queue import STTJob

BASE_URL = "http://testserver"
ADMIN_KEY = "super-secret-admin"


class FakeQueue:
    """Minimal fake of the STT queue for testing DLQ replay."""

    def __init__(self) -> None:
        self._jobs: dict[int, STTJob] = {}
        self.replayed: list[int] = []

    def add(self, job: STTJob) -> None:
        self._jobs[job.record_id] = job

    def replay_dlq_job(self, record_id: int) -> STTJob | None:
        job = self._jobs.get(record_id)
        if job is None:
            return None
        self.replayed.append(record_id)
        return job


@pytest.fixture(autouse=True)
def _configure_admin_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


@pytest.fixture()
def fake_queue() -> FakeQueue:
    queue = FakeQueue()
    queue.add(
        STTJob(
            record_id=123,
            call_id="call-123",
            recording_url="https://example.com/recording.mp3",
            engine="whisper",
            language="ru",
        )
    )
    return queue


@pytest.fixture()
def sqlite_engine() -> Engine:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AuditLog.__table__.create(bind=engine, checkfirst=True)
    configure_engine(engine)
    try:
        yield engine
    finally:
        configure_engine(default_engine)
        engine.dispose()


@pytest_asyncio.fixture()
async def api_client(sqlite_engine: Engine, fake_queue: FakeQueue) -> AsyncIterator[httpx.AsyncClient]:
    def override_get_session() -> Iterator[Session]:
        session = Session(bind=sqlite_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_stt_queue] = lambda: fake_queue

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        yield client

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_stt_queue, None)


@pytest.mark.asyncio
async def test_dlq_replay_requires_admin_credentials(
    api_client: httpx.AsyncClient,
) -> None:
    payload = {"record_id": 123, "reason": "manual replay"}

    missing_auth = await api_client.post("/api/v1/stt/dlq/replay", json=payload)
    assert missing_auth.status_code == 401
    assert missing_auth.json()["title"] == "Unauthorized"

    wrong_auth = await api_client.post(
        "/api/v1/stt/dlq/replay",
        json=payload,
        headers={"Authorization": "Bearer invalid"},
    )
    assert wrong_auth.status_code == 401
    assert wrong_auth.json()["title"] == "Unauthorized"


@pytest.mark.asyncio
async def test_dlq_replay_logs_audit_entry(
    api_client: httpx.AsyncClient,
    sqlite_engine: Engine,
    fake_queue: FakeQueue,
) -> None:
    headers = {
        "Authorization": f"Bearer {ADMIN_KEY}",
        "X-Admin-Actor": "operator-1",
    }
    payload = {"record_id": 123, "reason": "Manual retry after fix"}

    response = await api_client.post("/api/v1/stt/dlq/replay", json=payload, headers=headers)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "requeued"
    assert body["job"]["record_id"] == 123
    assert fake_queue.replayed == [123]

    session = Session(bind=sqlite_engine)
    try:
        entries = session.query(AuditLog).all()
    finally:
        session.close()

    assert len(entries) == 1
    entry = entries[0]
    assert entry.actor == "operator-1"
    assert entry.action == "stt_dlq_replay"
    assert entry.job_reference == "123"
    assert entry.reason == "Manual retry after fix"
    assert entry.job_payload["call_id"] == "call-123"
