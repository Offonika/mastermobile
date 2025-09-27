"""Allow missing_audio status in call_records CHECK constraint."""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_call_records_missing_audio"
down_revision = "0003_call_exports_call_records"
branch_labels = None
depends_on = None

CALL_RECORD_STATUS_CHECK = (
    "status IN ('pending','downloading','downloaded','transcribing','completed','skipped','error','missing_audio')"
)

PREVIOUS_CALL_RECORD_STATUS_CHECK = (
    "status IN ('pending','downloading','downloaded','transcribing','completed','skipped','error')"
)


def upgrade() -> None:
    op.drop_constraint("chk_call_records_status", "call_records", type_="check")
    op.create_check_constraint(
        "chk_call_records_status",
        "call_records",
        CALL_RECORD_STATUS_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint("chk_call_records_status", "call_records", type_="check")
    op.create_check_constraint(
        "chk_call_records_status",
        "call_records",
        PREVIOUS_CALL_RECORD_STATUS_CHECK,
    )
