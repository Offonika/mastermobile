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


class CourierStatus(str, Enum):
    """Lifecycle states of a courier in the Walking Warehouse."""

    ONBOARDING = "onboarding"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class DeliveryOrderStatus(str, Enum):
    """Workflow statuses for the delivery order lifecycle."""

    NEW = "new"
    PICKING = "picking"
    READY = "ready"
    PICKED_UP = "picked_up"
    ON_ROUTE = "on_route"
    DELIVERED = "delivered"
    CASH_RETURNED = "cash_returned"
    DONE = "done"
    FAILED = "failed"
    REFUSED = "refused"
    CANCELLED = "cancelled"


class DeliveryAssignmentStatus(str, Enum):
    """Workflow states for the courier task assignment."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DeliveryLogStatus(str, Enum):
    """High level result of a delivery workflow event."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


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

    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
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
            "attempts >= 0",
            name="chk_call_records_attempts_non_negative",
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
        Index(
            "uq_call_records_run_call_record",
            "run_id",
            "call_id",
            text("coalesce(record_id, '')"),
            unique=True,
        ),
        Index(
            "uq_call_records_call_id_recording_url",
            "call_id",
            "recording_url",
            unique=True,
            postgresql_where=text("recording_url IS NOT NULL"),
            sqlite_where=text("recording_url IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("call_exports.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    call_id: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[CallDirection] = mapped_column(
        _enum_type(CallDirection, name="call_direction", length=16),
        nullable=False,
    )
    from_number: Mapped[str] = mapped_column(Text, nullable=False)
    to_number: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    employee_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcription_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    currency_code: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        default="RUB",
        server_default=text("'RUB'"),
    )
    status: Mapped[CallRecordStatus] = mapped_column(
        _enum_type(CallRecordStatus, name="call_record_status", length=32),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
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
    transcript: Mapped["B24Transcript | None"] = relationship(
        back_populates="call_record",
        cascade="all, delete-orphan",
        uselist=False,
    )


class B24Transcript(Base):
    """Full text transcript linked to a Bitrix24 call record."""

    __tablename__ = "b24_transcripts"
    __table_args__ = (
        Index("uq_b24_transcripts_call_record_id", "call_record_id", unique=True),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    call_record_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("call_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    text_full: Mapped[str] = mapped_column(Text, nullable=False)
    text_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
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

    call_record: Mapped[CallRecord] = relationship(back_populates="transcript")


class Courier(Base):
    """Courier reference stored in the Walking Warehouse schema."""

    __tablename__ = "couriers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('onboarding','active','suspended','inactive')",
            name="chk_couriers_status",
        ),
        CheckConstraint(
            "length(trim(phone)) > 0",
            name="chk_couriers_phone_not_blank",
        ),
        Index("idx_couriers_status", "status"),
    )

    courier_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CourierStatus] = mapped_column(
        _enum_type(CourierStatus, name="courier_status", length=16),
        nullable=False,
        default=CourierStatus.ONBOARDING,
        server_default=CourierStatus.ONBOARDING.value,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
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

    orders: Mapped[list["DeliveryOrder"]] = relationship(
        back_populates="courier",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["DeliveryAssignment"]] = relationship(
        back_populates="courier",
        cascade="all, delete-orphan",
    )
    logs: Mapped[list["DeliveryLog"]] = relationship(back_populates="courier")


class DeliveryOrder(Base):
    """Delivery order orchestrated by the middleware."""

    __tablename__ = "delivery_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','picking','ready','picked_up','on_route','delivered','cash_returned','done','failed','refused','cancelled')",
            name="chk_delivery_orders_status",
        ),
        CheckConstraint(
            "delivery_price >= 0",
            name="chk_delivery_orders_delivery_price_non_negative",
        ),
        CheckConstraint(
            "cod_amount >= 0",
            name="chk_delivery_orders_cod_amount_non_negative",
        ),
        Index(
            "idx_delivery_orders_status_active",
            "status",
            postgresql_where=text(
                "status IN ('new','picking','ready','picked_up','on_route','delivered')"
            ),
            sqlite_where=text(
                "status IN ('new','picking','ready','picked_up','on_route','delivered')"
            ),
        ),
        Index("idx_delivery_orders_courier_status", "courier_id", "status"),
        Index(
            "uq_delivery_orders_external_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
            sqlite_where=text("external_id IS NOT NULL"),
        ),
    )

    order_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DeliveryOrderStatus] = mapped_column(
        _enum_type(DeliveryOrderStatus, name="delivery_order_status", length=32),
        nullable=False,
        default=DeliveryOrderStatus.NEW,
        server_default=DeliveryOrderStatus.NEW.value,
    )
    courier_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("couriers.courier_id", ondelete="SET NULL"),
        nullable=True,
    )
    delivery_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    cod_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
    )
    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="RUB",
        server_default=text("'RUB'"),
    )
    expected_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
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

    courier: Mapped[Courier | None] = relationship(
        back_populates="orders",
        lazy="joined",
    )
    assignments: Mapped[list["DeliveryAssignment"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    logs: Mapped[list["DeliveryLog"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class DeliveryAssignment(Base):
    """Link between a courier and delivery order with status tracking."""

    __tablename__ = "delivery_assignments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','accepted','declined','in_progress','completed','cancelled')",
            name="chk_delivery_assignments_status",
        ),
        Index("idx_delivery_assignments_order_status", "order_id", "status"),
        Index(
            "uq_delivery_assignments_active",
            "order_id",
            "courier_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending','accepted','in_progress')"
            ),
            sqlite_where=text(
                "status IN ('pending','accepted','in_progress')"
            ),
        ),
    )

    assignment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    order_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("delivery_orders.order_id", ondelete="CASCADE"),
        nullable=False,
    )
    courier_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("couriers.courier_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[DeliveryAssignmentStatus] = mapped_column(
        _enum_type(
            DeliveryAssignmentStatus,
            name="delivery_assignment_status",
            length=32,
        ),
        nullable=False,
        default=DeliveryAssignmentStatus.PENDING,
        server_default=DeliveryAssignmentStatus.PENDING.value,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
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

    order: Mapped[DeliveryOrder] = relationship(back_populates="assignments")
    courier: Mapped[Courier] = relationship(back_populates="assignments")
    logs: Mapped[list["DeliveryLog"]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
    )


class DeliveryLog(Base):
    """Auditable log entry for a delivery order or assignment event."""

    __tablename__ = "delivery_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('info','success','warning','error')",
            name="chk_delivery_logs_status",
        ),
        Index("idx_delivery_logs_order_created", "order_id", "created_at"),
        Index("idx_delivery_logs_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    order_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("delivery_orders.order_id", ondelete="CASCADE"),
        nullable=False,
    )
    assignment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("delivery_assignments.assignment_id", ondelete="SET NULL"),
        nullable=True,
    )
    courier_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("couriers.courier_id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[DeliveryLogStatus] = mapped_column(
        _enum_type(DeliveryLogStatus, name="delivery_log_status", length=16),
        nullable=False,
        default=DeliveryLogStatus.INFO,
        server_default=DeliveryLogStatus.INFO.value,
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONBType,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    order: Mapped[DeliveryOrder] = relationship(back_populates="logs")
    assignment: Mapped[DeliveryAssignment | None] = relationship(
        back_populates="logs"
    )
    courier: Mapped[Courier | None] = relationship(back_populates="logs")
