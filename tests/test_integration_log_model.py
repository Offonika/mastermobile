"""IntegrationLog ORM synchronisation tests."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.mw.src.db.models import Base, IntegrationDirection, IntegrationLog


def test_integration_log_roundtrip() -> None:
    """The IntegrationLog ORM model matches the database schema."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[IntegrationLog.__table__])

    log_entry = IntegrationLog(
        direction=IntegrationDirection.OUTBOUND,
        external_system="b24",
        endpoint="/sync/orders",
        status="error",
        status_code=None,
        correlation_id=None,
        resource_ref="order-42",
        request={"payload": True},
        response={"result": "error"},
        error_code="E_CONN_TIMEOUT",
        retry_count=None,
    )

    with Session(engine) as session:
        session.add(log_entry)
        session.commit()

        stored_log = session.scalar(
            select(IntegrationLog).where(IntegrationLog.id == log_entry.id)
        )

    assert stored_log is not None
    assert stored_log.external_system == "b24"
    assert stored_log.status == "error"
    assert stored_log.status_code is None
    assert stored_log.request == {"payload": True}
    assert stored_log.response == {"result": "error"}
    assert stored_log.error_code == "E_CONN_TIMEOUT"
    assert stored_log.retry_count is None
    assert stored_log.resource_ref == "order-42"
