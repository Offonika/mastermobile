"""Create tables for Bitrix24 call exports and records."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_call_exports_call_records"
down_revision = "0002_return_lines_defect_reason_check"
branch_labels = None
depends_on = None


CALL_EXPORT_STATUS_CHECK = (
    "status IN ('pending','in_progress','completed','error','cancelled')"
)

CALL_RECORD_STATUS_CHECK = (
    "status IN ('pending','downloading','downloaded','transcribing','completed','skipped','error','missing_audio')"
)


def upgrade() -> None:
    op.create_table(
        "call_exports",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("period_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("period_to", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("core.users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(CALL_EXPORT_STATUS_CHECK, name="chk_call_exports_status"),
        sa.CheckConstraint(
            "period_to >= period_from", name="chk_call_exports_period"
        ),
    )

    op.create_table(
        "call_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("call_id", sa.Text(), nullable=False),
        sa.Column("record_id", sa.Text(), nullable=True),
        sa.Column("call_started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=False),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("transcript_path", sa.Text(), nullable=True),
        sa.Column("transcript_lang", sa.Text(), nullable=True),
        sa.Column("checksum", sa.Text(), nullable=True),
        sa.Column("cost_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "cost_currency",
            sa.String(length=3),
            nullable=True,
            server_default=sa.text("'RUB'"),
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_attempt_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["call_exports.run_id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "duration_sec >= 0", name="chk_call_records_duration_non_negative"
        ),
        sa.CheckConstraint(
            "attempts >= 0", name="chk_call_records_attempts_non_negative"
        ),
        sa.CheckConstraint(
            CALL_RECORD_STATUS_CHECK, name="chk_call_records_status"
        ),
    )

    op.create_index(
        "idx_call_exports_status_active",
        "call_exports",
        ["status"],
        postgresql_where=sa.text(
            "status IN ('pending','in_progress','error')"
        ),
    )

    op.create_index(
        "idx_call_records_status_run",
        "call_records",
        ["status", "run_id"],
        postgresql_where=sa.text(
            "status IN ('pending','downloading','transcribing','error')"
        ),
    )

    op.create_index(
        "idx_call_records_checksum",
        "call_records",
        ["checksum"],
        postgresql_where=sa.text("checksum IS NOT NULL"),
    )

    op.create_index(
        "uq_call_records_run_call_record",
        "call_records",
        ["run_id", "call_id", sa.text("coalesce(record_id, '')")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_call_records_run_call_record", table_name="call_records")
    op.drop_index("idx_call_records_checksum", table_name="call_records")
    op.drop_index("idx_call_records_status_run", table_name="call_records")
    op.drop_index("idx_call_exports_status_active", table_name="call_exports")
    op.drop_table("call_records")
    op.drop_table("call_exports")
