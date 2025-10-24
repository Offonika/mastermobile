"""Add direction and phone numbers to call records."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_call_records_direction_and_numbers"
down_revision = "0003_call_exports_call_records"
branch_labels = None
depends_on = None


CALL_RECORD_DIRECTION_CHECK = (
    "direction IN ('inbound','outbound','internal')"
)
CALL_RECORD_FROM_NUMBER_CHECK = "length(trim(from_number)) > 0"
CALL_RECORD_TO_NUMBER_CHECK = "length(trim(to_number)) > 0"


def upgrade() -> None:
    op.add_column(
        "call_records",
        sa.Column(
            "direction",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "call_records",
        sa.Column(
            "from_number",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "call_records",
        sa.Column(
            "to_number",
            sa.Text(),
            nullable=True,
        ),
    )

    op.execute("UPDATE call_records SET direction = 'inbound' WHERE direction IS NULL")
    op.execute("UPDATE call_records SET from_number = 'unknown' WHERE from_number IS NULL")
    op.execute("UPDATE call_records SET to_number = 'unknown' WHERE to_number IS NULL")

    op.alter_column("call_records", "direction", nullable=False)
    op.alter_column("call_records", "from_number", nullable=False)
    op.alter_column("call_records", "to_number", nullable=False)

    op.create_check_constraint(
        "chk_call_records_direction",
        "call_records",
        CALL_RECORD_DIRECTION_CHECK,
    )
    op.create_check_constraint(
        "chk_call_records_from_number_not_blank",
        "call_records",
        CALL_RECORD_FROM_NUMBER_CHECK,
    )
    op.create_check_constraint(
        "chk_call_records_to_number_not_blank",
        "call_records",
        CALL_RECORD_TO_NUMBER_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint(
        "chk_call_records_to_number_not_blank",
        "call_records",
        type_="check",
    )
    op.drop_constraint(
        "chk_call_records_from_number_not_blank",
        "call_records",
        type_="check",
    )
    op.drop_constraint(
        "chk_call_records_direction",
        "call_records",
        type_="check",
    )
    op.drop_column("call_records", "to_number")
    op.drop_column("call_records", "from_number")
    op.drop_column("call_records", "direction")
