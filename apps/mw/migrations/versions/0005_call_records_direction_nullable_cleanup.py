"""Ensure call record direction and numbers are non-null enums."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_call_records_direction_nullable_cleanup"
down_revision = (
    "0004_call_records_missing_audio",
    "0004_call_records_direction_and_numbers",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE call_records SET direction = 'inbound' WHERE direction IS NULL")
    op.execute("UPDATE call_records SET from_number = 'unknown' WHERE from_number IS NULL")
    op.execute("UPDATE call_records SET to_number = 'unknown' WHERE to_number IS NULL")

    op.alter_column(
        "call_records",
        "direction",
        existing_type=sa.Text(),
        type_=sa.String(length=16),
        nullable=False,
        postgresql_using="direction::varchar(16)",
    )
    op.alter_column(
        "call_records",
        "from_number",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.alter_column(
        "call_records",
        "to_number",
        existing_type=sa.Text(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "call_records",
        "to_number",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.alter_column(
        "call_records",
        "from_number",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.alter_column(
        "call_records",
        "direction",
        existing_type=sa.String(length=16),
        type_=sa.Text(),
        nullable=True,
        postgresql_using="direction::text",
    )
