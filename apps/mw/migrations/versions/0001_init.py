"""Initial database schema for returns flow and integration log."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


RETURNS_STATUS_CHECK = "status IN ('return_ready', 'accepted', 'return_rejected')"
RETURNS_ACTIVE_STATUSES = "status IN ('return_ready', 'accepted')"


def upgrade() -> None:
    op.create_table(
        "returns",
        sa.Column("return_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("courier_id", sa.BigInteger(), nullable=True),
        sa.Column("order_id_1c", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'return_ready'"),
        ),
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
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint(RETURNS_STATUS_CHECK, name="chk_returns_status"),
    )

    op.create_table(
        "return_lines",
        sa.Column("line_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("return_id", sa.BigInteger(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("qty", sa.Numeric(12, 3), nullable=False),
        sa.Column(
            "quality",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'new'"),
        ),
        sa.Column("reason_id", sa.String(length=64), nullable=True),
        sa.Column("reason_note", sa.Text(), nullable=True),
        sa.Column("imei", sa.String(length=32), nullable=True),
        sa.Column("serial", sa.String(length=64), nullable=True),
        sa.Column(
            "photos",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
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
        sa.ForeignKeyConstraint(
            ("return_id",),
            ["returns.return_id"],
            ondelete="CASCADE",
            name="return_lines_return_id_fkey",
        ),
        sa.CheckConstraint("qty >= 0", name="chk_return_qty_nonneg"),
        sa.CheckConstraint(
            "quality <> 'defect' OR reason_id IS NOT NULL",
            name="chk_return_defect_reason",
        ),
        sa.CheckConstraint(
            "quality IN ('new', 'defect')",
            name="chk_return_quality",
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
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column(
            "request",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "response",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("extra", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint("retry_count >= 0", name="chk_integration_log_retry_nonneg"),
    )

    op.create_index(
        "idx_returns_status_created",
        "returns",
        ["status", "created_at"],
        postgresql_where=sa.text(RETURNS_ACTIVE_STATUSES),
    )
    op.create_index(
        "idx_returns_status_uat",
        "returns",
        ["status", "updated_at"],
        postgresql_where=sa.text(RETURNS_ACTIVE_STATUSES),
    )
    op.create_index(
        "idx_returns_ready",
        "returns",
        ["return_id"],
        postgresql_where=sa.text("status = 'return_ready'"),
    )

    op.create_index(
        "idx_integration_log_req_gin",
        "integration_log",
        ["request"],
        postgresql_using="gin",
        postgresql_ops={"request": "jsonb_path_ops"},
    )
    op.create_index(
        "idx_integration_log_resp_gin",
        "integration_log",
        ["response"],
        postgresql_using="gin",
        postgresql_ops={"response": "jsonb_path_ops"},
    )


def downgrade() -> None:
    op.drop_index("idx_integration_log_resp_gin", table_name="integration_log")
    op.drop_index("idx_integration_log_req_gin", table_name="integration_log")
    op.drop_index("idx_returns_ready", table_name="returns")
    op.drop_index("idx_returns_status_uat", table_name="returns")
    op.drop_index("idx_returns_status_created", table_name="returns")

    op.drop_table("integration_log")
    op.drop_table("return_lines")
    op.drop_table("returns")
