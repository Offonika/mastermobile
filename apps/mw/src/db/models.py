"""SQLAlchemy models for MasterMobile middleware."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
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


class CallExportStatus(str, Enum):
    """Lifecycle states for bulk Bitrix24 call exports."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class CallRecordStatus(str, Enum):
    """Processing state for each exported call record."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    ERROR = "error"
    MISSING_AUDIO = "missing_audio"


class CallDirection(str, Enum):
    """Direction of a Bitrix24 call."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


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


class CallExport(Base):
    """Run of Bitrix24 batch call export."""

    __tablename__ = "call_exports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','in_progress','completed','error','cancelled')",
            name="chk_call_exports_status",
        ),
        CheckConstraint(
            "period_to >= period_from",
            name="chk_call_exports_period",
        ),
        Index(
            "idx_call_exports_status_active",
            "status",
            postgresql_where=text(
                "status IN ('pending','in_progress','error')"
            ),
        ),
    )

    run_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    period_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    period_to: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[CallExportStatus] = mapped_column(
        _enum_type(CallExportStatus, name="call_export_status", length=32),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("core.users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    options: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType,
        nullable=True,
    )
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

    records: Mapped[list[CallRecord]] = relationship(
        back_populates="export",
        cascade="all, delete-orphan",
    )


class CallRecord(Base):
    """Single Bitrix24 call entry that belongs to a call export run."""

    __tablename__ = "call_records"
    __table_args__ = (
        CheckConstraint(
            "duration_sec >= 0",
            name="chk_call_records_duration_non_negative",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="chk_call_records_retry_count_non_negative",
        ),
        CheckConstraint(
            "status IN ('pending','downloading','downloaded','transcribing','completed','skipped','error','missing_audio')",
            name="chk_call_records_status",
        ),
        CheckConstraint(
            "direction IN ('inbound','outbound','internal')",
            name="chk_call_records_direction",
        ),
        CheckConstraint(
            "length(trim(from_number)) > 0",
            name="chk_call_records_from_number_not_blank",
        ),
        CheckConstraint(
            "length(trim(to_number)) > 0",
            name="chk_call_records_to_number_not_blank",
        ),
        Index(
            "idx_call_records_status_run",
            "status",
            "run_id",
            postgresql_where=text(
                "status IN ('pending','downloading','transcribing','error')"
            ),
        ),
        Index(
            "idx_call_records_checksum",
            "checksum",
            postgresql_where=text("checksum IS NOT NULL"),
        ),
        UniqueConstraint(
            "run_id",
            "call_id",
            name="uq_call_records_run_call",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("call_exports.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    call_id: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    direction: Mapped[CallDirection] = mapped_column(
        _enum_type(CallDirection, name="call_direction", length=16),
        nullable=False,
    )
    employee_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_number: Mapped[str] = mapped_column(Text, nullable=False)
    to_number: Mapped[str] = mapped_column(Text, nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    recording_url: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcription_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default=text("'RUB'"),
    )
    status: Mapped[CallRecordStatus] = mapped_column(
        _enum_type(CallRecordStatus, name="call_record_status", length=32),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    last_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
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

    export: Mapped[CallExport] = relationship(back_populates="records")
