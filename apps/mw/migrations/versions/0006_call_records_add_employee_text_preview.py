"""Add employee, text preview and rename transcript/cost fields."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_call_records_add_employee_text_preview"
down_revision = "0005_call_records_direction_nullable_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("call_records", sa.Column("employee_id", sa.Text(), nullable=True))
    op.add_column("call_records", sa.Column("summary_path", sa.Text(), nullable=True))
    op.add_column("call_records", sa.Column("text_preview", sa.Text(), nullable=True))
    op.alter_column("call_records", "transcript_lang", new_column_name="language")
    op.alter_column("call_records", "cost_amount", new_column_name="transcription_cost")
    op.alter_column("call_records", "cost_currency", new_column_name="currency_code")


def downgrade() -> None:
    op.alter_column("call_records", "currency_code", new_column_name="cost_currency")
    op.alter_column("call_records", "transcription_cost", new_column_name="cost_amount")
    op.alter_column("call_records", "language", new_column_name="transcript_lang")
    op.drop_column("call_records", "text_preview")
    op.drop_column("call_records", "summary_path")
    op.drop_column("call_records", "employee_id")
