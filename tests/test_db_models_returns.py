"""Integration tests for ORM mappings of returns tables."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.mw.src.db.models import (
    Base,
    Return,
    ReturnLine,
    ReturnLineQuality,
    ReturnSource,
    ReturnStatus,
)


def test_return_roundtrip_matches_schema() -> None:
    """Persist and load return with lines to ensure UUID/relationships match migration."""

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=[Return.__table__, ReturnLine.__table__])

    return_id = uuid4()
    reason_id = uuid4()

    with Session(engine) as session:
        return_obj = Return(
            return_id=return_id,
            status=ReturnStatus.RETURN_READY,
            source=ReturnSource.WAREHOUSE,
            courier_id="courier-42",
            order_id_1c="order-1c",
            comment="Quality check",
        )
        return_obj.lines.append(
            ReturnLine(
                id=1,
                line_id="line-1",
                sku="sku-1",
                qty=Decimal("2.500"),
                quality=ReturnLineQuality.NEW,
                reason_id=reason_id,
                reason_note="Packaging damaged",
                photos=None,
                imei="123456789012345",
                serial="SN123456789",
            )
        )

        session.add(return_obj)
        session.commit()
        session.expunge_all()

        loaded = session.scalars(
            select(Return).where(Return.return_id == return_id)
        ).one()

        assert loaded.return_id == return_id
        assert loaded.lines, "Return should contain associated lines"

        line = loaded.lines[0]
        assert line.return_id == return_id
        assert line.line_id == "line-1"
        assert line.qty == Decimal("2.500")
        assert isinstance(line.qty, Decimal)
        assert line.quality is ReturnLineQuality.NEW
        assert line.reason_id == reason_id
        assert line.photos is None
        assert line.serial == "SN123456789"

    engine.dispose()


def test_return_line_defect_requires_reason() -> None:
    """Ensure DB refuses defect lines without linked reason."""

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=[Return.__table__, ReturnLine.__table__])

    with Session(engine) as session:
        return_obj = Return(
            return_id=uuid4(),
            status=ReturnStatus.RETURN_READY,
            source=ReturnSource.WAREHOUSE,
            courier_id="courier-13",
        )
        return_obj.lines.append(
            ReturnLine(
                line_id="line-defect",
                sku="sku-defect",
                qty=Decimal("1.000"),
                quality=ReturnLineQuality.DEFECT,
                reason_id=None,
            )
        )

        session.add(return_obj)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()

    engine.dispose()
