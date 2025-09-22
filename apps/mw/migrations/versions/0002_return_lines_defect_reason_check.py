"""Ensure return lines always persist a non-empty reason code."""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_return_lines_defect_reason_check"
down_revision = "0001_init"
branch_labels = None
depends_on = None


CHECK_RETURN_LINES_REASON_CODE = "length(trim(reason_code)) > 0"


def upgrade() -> None:
    op.create_check_constraint(
        "chk_return_lines_reason_code_not_blank",
        "return_lines",
        CHECK_RETURN_LINES_REASON_CODE,
    )


def downgrade() -> None:
    op.drop_constraint(
        "chk_return_lines_reason_code_not_blank",
        "return_lines",
        type_="check",
    )
