"""SQLAlchemy models for MasterMobile middleware."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for all models."""


class ReturnStatus(str, Enum):
    """Possible workflow statuses for the return document."""

    RETURN_READY = "return_ready"
    ACCEPTED = "accepted"
    RETURN_REJECTED = "return_rejected"


class ReturnSource(str, Enum):
    """Channels that can initiate a return."""

    WIDGET = "widget"
    CALL_CENTER = "call_center"
    WAREHOUSE = "warehouse"


class ReturnLineQuality(str, Enum):
    """Quality flags for returned items."""

    NEW = "new"
    DEFECT = "defect"


class IntegrationDirection(str, Enum):
    """Direction of the integration call captured in the log."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Return(Base):
    """Return document acknowledged by the middleware."""

    __tablename__ = "returns"

    return_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[ReturnStatus] = mapped_column(
        SqlEnum(ReturnStatus, name="return_status"),
        nullable=False,
        default=ReturnStatus.RETURN_READY,
        server_default=ReturnStatus.RETURN_READY.value,
    )
    source: Mapped[ReturnSource] = mapped_column(
        SqlEnum(ReturnSource, name="return_source"),
        nullable=False,
    )
    courier_id: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id_1c: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    lines: Mapped[list["ReturnLine"]] = relationship(
        back_populates="return_",
        cascade="all, delete-orphan",
    )


class ReturnLine(Base):
    """Line of a return document (single SKU/IMEI)."""

    __tablename__ = "return_lines"
    __table_args__ = (
        CheckConstraint("qty >= 0", name="chk_return_qty_nonneg"),
        CheckConstraint("quality <> 'defect' OR reason_id IS NOT NULL", name="chk_return_defect_reason"),
    )

    line_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    return_id: Mapped[int] = mapped_column(
        ForeignKey("returns.return_id", ondelete="CASCADE"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    quality: Mapped[ReturnLineQuality] = mapped_column(
        SqlEnum(ReturnLineQuality, name="return_line_quality"),
        nullable=False,
        default=ReturnLineQuality.NEW,
        server_default=ReturnLineQuality.NEW.value,
    )
    reason_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    photos: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    imei: Mapped[str | None] = mapped_column(String(32), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(64), nullable=True)

    return_: Mapped[Return] = relationship(back_populates="lines")


class IntegrationLog(Base):
    """Structured integration log entry persisted in PostgreSQL."""

    __tablename__ = "integration_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    direction: Mapped[IntegrationDirection] = mapped_column(
        SqlEnum(IntegrationDirection, name="integration_direction"),
        nullable=False,
    )
    system: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
