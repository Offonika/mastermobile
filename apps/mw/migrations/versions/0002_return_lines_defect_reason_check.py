"""Add check constraint ensuring defect lines have a reason."""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_return_lines_defect_reason_check"
down_revision = "0001_init"
branch_labels = None
depends_on = None


CHECK_RETURN_LINES_DEFECT_REASON = "quality <> 'defect' OR reason_id IS NOT NULL"


def upgrade() -> None:
    op.create_check_constraint(
        "chk_return_lines_defect_reason",
        "return_lines",
        CHECK_RETURN_LINES_DEFECT_REASON,
    )


def downgrade() -> None:
    op.drop_constraint(
        "chk_return_lines_defect_reason",
        "return_lines",
        type_="check",
    )
