"""Integration tests for ORM mappings of integration_log table."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from apps.mw.src.db.models import (
    Base,
    IntegrationDirection,
    IntegrationExternalSystem,
    IntegrationLog,
    IntegrationStatus,
)


def test_integration_log_roundtrip_matches_schema() -> None:
    """Persist and load integration log ensuring fields match migration schema."""

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=[IntegrationLog.__table__])

    with Session(engine) as session:
        log_entry = IntegrationLog(
            id=1,
            direction=IntegrationDirection.INBOUND,
            external_system=IntegrationExternalSystem.ONE_C,
            endpoint="/api/v1/returns",
            status=IntegrationStatus.SUCCESS,
            status_code=None,
            correlation_id="corr-123",
            resource_ref="returns/123",
            request=None,
            response={"result": "ok"},
            error_code=None,
            retry_count=0,
        )
        session.add(log_entry)
        session.commit()
        log_id = log_entry.id
        session.expunge_all()

        loaded = session.scalars(
            select(IntegrationLog).where(IntegrationLog.id == log_id)
        ).one()

        assert loaded.direction is IntegrationDirection.INBOUND
        assert loaded.external_system is IntegrationExternalSystem.ONE_C
        assert loaded.endpoint == "/api/v1/returns"
        assert loaded.status is IntegrationStatus.SUCCESS
        assert loaded.status_code is None
        assert loaded.correlation_id == "corr-123"
        assert loaded.resource_ref == "returns/123"
        assert loaded.request is None
        assert loaded.response == {"result": "ok"}
        assert loaded.error_code is None
        assert loaded.retry_count == 0

    engine.dispose()
