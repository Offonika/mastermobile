"""Tighten call record direction and phone constraints."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_call_records_direction_constraints"
down_revision = ("0004_call_records_missing_audio", "0004_call_records_direction_and_numbers")
branch_labels = None
depends_on = None

DIRECTION_CHECK = "direction IN ('inbound','outbound','internal')"
FROM_NUMBER_CHECK = "length(trim(from_number)) > 0"
TO_NUMBER_CHECK = "length(trim(to_number)) > 0"


def upgrade() -> None:
    op.execute("UPDATE call_records SET direction = 'inbound' WHERE direction IS NULL")
    op.execute(
        """
        UPDATE call_records
        SET from_number = 'unknown'
        WHERE from_number IS NULL OR length(trim(from_number)) = 0
        """
    )
    op.execute(
        """
        UPDATE call_records
        SET to_number = 'unknown'
        WHERE to_number IS NULL OR length(trim(to_number)) = 0
        """
    )

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

    op.drop_constraint("chk_call_records_direction", "call_records", type_="check")
    op.create_check_constraint(
        "chk_call_records_direction",
        "call_records",
        DIRECTION_CHECK,
    )
    op.drop_constraint(
        "chk_call_records_from_number_not_blank",
        "call_records",
        type_="check",
    )
    op.create_check_constraint(
        "chk_call_records_from_number_not_blank",
        "call_records",
        FROM_NUMBER_CHECK,
    )
    op.drop_constraint(
        "chk_call_records_to_number_not_blank",
        "call_records",
        type_="check",
    )
    op.create_check_constraint(
        "chk_call_records_to_number_not_blank",
        "call_records",
        TO_NUMBER_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint("chk_call_records_to_number_not_blank", "call_records", type_="check")
    op.drop_constraint("chk_call_records_from_number_not_blank", "call_records", type_="check")
    op.drop_constraint("chk_call_records_direction", "call_records", type_="check")

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

    op.create_check_constraint(
        "chk_call_records_direction",
        "call_records",
        DIRECTION_CHECK,
    )
    op.create_check_constraint(
        "chk_call_records_from_number_not_blank",
        "call_records",
        FROM_NUMBER_CHECK,
    )
    op.create_check_constraint(
        "chk_call_records_to_number_not_blank",
        "call_records",
        TO_NUMBER_CHECK,
    )
