"""Initial database schema for MasterMobile returns flow."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

RETURNS_STATUS_CHECK = "status IN ('pending', 'accepted', 'rejected', 'cancelled')"
RETURNS_SOURCE_CHECK = "source IN ('widget', 'call_center', 'warehouse')"
RETURN_LINES_QUALITY_CHECK = "quality IN ('new', 'defect', 'unknown')"
INTEGRATION_LOG_DIRECTION_CHECK = "direction IN ('inbound', 'outbound')"
INTEGRATION_LOG_SYSTEM_CHECK = "external_system IN ('1c', 'b24', 'warehouse')"
INTEGRATION_LOG_STATUS_CHECK = "status IN ('success', 'error', 'retry')"
TASK_EVENTS_TYPE_CHECK = "type IN ('status', 'photo', 'geo', 'comment')"


def upgrade() -> None:
    op.create_table(
        "returns",
        sa.Column(
            "return_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("order_id_1c", sa.Text(), nullable=True),
        sa.Column("courier_id", sa.Text(), nullable=False),
        sa.Column("manager_id", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(RETURNS_STATUS_CHECK, name="chk_returns_status"),
        sa.CheckConstraint(RETURNS_SOURCE_CHECK, name="chk_returns_source"),
    )

    op.create_table(
        "return_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("return_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_id", sa.Text(), nullable=False),
        sa.Column("sku", sa.Text(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("quality", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=False),
        sa.Column("reason_note", sa.Text(), nullable=True),
        sa.Column("photos", postgresql.JSONB(), nullable=True),
        sa.Column("imei", sa.Text(), nullable=True),
        sa.Column("serial", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["return_id"],
            ["returns.return_id"],
            ondelete="CASCADE",
            name="return_lines_return_id_fkey",
        ),
        sa.CheckConstraint(
            "qty > 0",
            name="chk_return_lines_qty_positive",
        ),
        sa.CheckConstraint(
            RETURN_LINES_QUALITY_CHECK,
            name="chk_return_lines_quality",
        ),
    )

    op.create_table(
        "integration_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("external_system", sa.String(length=32), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("resource_ref", sa.Text(), nullable=True),
        sa.Column("request", postgresql.JSONB(), nullable=True),
        sa.Column("response", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            INTEGRATION_LOG_DIRECTION_CHECK,
            name="chk_integration_log_direction",
        ),
        sa.CheckConstraint(
            INTEGRATION_LOG_SYSTEM_CHECK,
            name="chk_integration_log_external_system",
        ),
        sa.CheckConstraint(
            INTEGRATION_LOG_STATUS_CHECK,
            name="chk_integration_log_status",
        ),
        sa.CheckConstraint(
            "retry_count IS NULL OR retry_count >= 0",
            name="chk_integration_log_retry_count",
        ),
    )

    op.create_table(
        "task_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("task_id_b24", sa.Text(), nullable=False),
        sa.Column("return_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=True, unique=True),
        sa.ForeignKeyConstraint(
            ["return_id"],
            ["returns.return_id"],
            ondelete="SET NULL",
            name="task_events_return_id_fkey",
        ),
        sa.CheckConstraint(TASK_EVENTS_TYPE_CHECK, name="chk_task_events_type"),
    )

    op.create_index(
        "ix_returns_status",
        "returns",
        ["status"],
    )
    op.create_index(
        "ix_return_lines_return_id",
        "return_lines",
        ["return_id"],
    )
    op.create_index(
        "ix_integration_log_resource_ref",
        "integration_log",
        ["resource_ref"],
    )
    op.create_index(
        "ix_integration_log_ts",
        "integration_log",
        ["ts"],
    )
    op.create_index(
        "ix_integration_log_status_error",
        "integration_log",
        ["status"],
        postgresql_where=sa.text("status = 'error'"),
    )
    op.create_index(
        "ix_task_events_return_id",
        "task_events",
        ["return_id"],
    )
    op.create_index(
        "ix_task_events_task_id_b24",
        "task_events",
        ["task_id_b24"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_events_task_id_b24", table_name="task_events")
    op.drop_index("ix_task_events_return_id", table_name="task_events")
    op.drop_table("task_events")

    op.drop_index("ix_integration_log_status_error", table_name="integration_log")
    op.drop_index("ix_integration_log_ts", table_name="integration_log")
    op.drop_index("ix_integration_log_resource_ref", table_name="integration_log")
    op.drop_table("integration_log")

    op.drop_index("ix_return_lines_return_id", table_name="return_lines")
    op.drop_table("return_lines")

    op.drop_index("ix_returns_status", table_name="returns")
    op.drop_table("returns")
