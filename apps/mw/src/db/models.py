"""SQLAlchemy models for MasterMobile middleware."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for all models."""


class ReturnStatus(str, Enum):
    """Possible workflow statuses for the return document."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ReturnSource(str, Enum):
    """Channels that can initiate a return."""

    WIDGET = "widget"
    CALL_CENTER = "call_center"
    WAREHOUSE = "warehouse"


class ReturnLineQuality(str, Enum):
    """Quality flags for returned items."""

    NEW = "new"
    DEFECT = "defect"
    UNKNOWN = "unknown"


class IntegrationDirection(str, Enum):
    """Direction of the integration call captured in the log."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class IntegrationExternalSystem(str, Enum):
    """External systems participating in integrations."""

    ONE_C = "1c"
    B24 = "b24"
    WAREHOUSE = "warehouse"


class IntegrationStatus(str, Enum):
    """Outcome status of the integration interaction."""

    SUCCESS = "success"
    ERROR = "error"
    RETRY = "retry"


JSONBType = JSONB().with_variant(SQLiteJSON(), "sqlite")


def _enum_type(enum_cls: type[Enum], *, name: str, length: int) -> SqlEnum:
    """Create a string-backed SQL enum preserving explicit values."""

    return SqlEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=False,
        length=length,
        values_callable=lambda obj: [member.value for member in obj],
        validate_strings=True,
    )


class Return(Base):
    """Return document acknowledged by the middleware."""

    __tablename__ = "returns"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name="chk_returns_status",
        ),
        CheckConstraint(
            "source IN ('widget', 'call_center', 'warehouse')",
            name="chk_returns_source",
        ),
    )

    return_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    status: Mapped[ReturnStatus] = mapped_column(
        _enum_type(ReturnStatus, name="return_status", length=32),
        nullable=False,
        default=ReturnStatus.PENDING,
        server_default=ReturnStatus.PENDING.value,
    )
    source: Mapped[ReturnSource] = mapped_column(
        _enum_type(ReturnSource, name="return_source", length=32),
        nullable=False,
    )
    courier_id: Mapped[str] = mapped_column(Text, nullable=False)
    order_id_1c: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_id: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    lines: Mapped[list[ReturnLine]] = relationship(
        back_populates="return_",
        cascade="all, delete-orphan",
    )


class ReturnLine(Base):
    """Line of a return document (single SKU/IMEI)."""

    __tablename__ = "return_lines"
    __table_args__ = (
        CheckConstraint("qty > 0", name="chk_return_lines_qty_positive"),
        CheckConstraint(
            "quality IN ('new', 'defect', 'unknown')",
            name="chk_return_lines_quality",
        ),
        CheckConstraint(
            "length(trim(reason_code)) > 0",
            name="chk_return_lines_reason_code_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    line_id: Mapped[str] = mapped_column(Text, nullable=False)
    return_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("returns.return_id", ondelete="CASCADE"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    quality: Mapped[ReturnLineQuality] = mapped_column(
        _enum_type(ReturnLineQuality, name="return_line_quality", length=16),
        nullable=False,
    )
    reason_code: Mapped[str] = mapped_column(Text, nullable=False)
    reason_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    photos: Mapped[list[str] | None] = mapped_column(JSONBType, nullable=True)
    imei: Mapped[str | None] = mapped_column(Text, nullable=True)
    serial: Mapped[str | None] = mapped_column(Text, nullable=True)

    return_: Mapped[Return] = relationship(back_populates="lines")


class IntegrationLog(Base):
    """Structured integration log entry persisted in PostgreSQL."""

    __tablename__ = "integration_log"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('inbound', 'outbound')",
            name="chk_integration_log_direction",
        ),
        CheckConstraint(
            "external_system IN ('1c', 'b24', 'warehouse')",
            name="chk_integration_log_external_system",
        ),
        CheckConstraint(
            "status IN ('success', 'error', 'retry')",
            name="chk_integration_log_status",
        ),
        CheckConstraint(
            "retry_count IS NULL OR retry_count >= 0",
            name="chk_integration_log_retry_count",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    direction: Mapped[IntegrationDirection] = mapped_column(
        _enum_type(IntegrationDirection, name="integration_direction", length=16),
        nullable=False,
    )
    external_system: Mapped[IntegrationExternalSystem] = mapped_column(
        _enum_type(IntegrationExternalSystem, name="integration_external_system", length=32),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[IntegrationStatus] = mapped_column(
        _enum_type(IntegrationStatus, name="integration_status", length=32),
        nullable=False,
    )
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    request: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONBType, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
