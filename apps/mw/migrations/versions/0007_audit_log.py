"""Create audit_log table for administrative actions."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

# revision identifiers, used by Alembic.
revision = "0007_audit_log"
down_revision = (
    "0006_call_records_add_employee_text_preview",
    "0006_call_records_unique_recording_url",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = JSONB().with_variant(SQLiteJSON(), "sqlite")

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("job_reference", sa.Text(), nullable=False),
        sa.Column("job_payload", json_type, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "length(trim(actor)) > 0",
            name="chk_audit_log_actor_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(action)) > 0",
            name="chk_audit_log_action_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(job_reference)) > 0",
            name="chk_audit_log_job_reference_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0",
            name="chk_audit_log_reason_not_blank",
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
