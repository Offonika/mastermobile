"""Deprecated migration kept for history after schema consolidation."""
from __future__ import annotations


# revision identifiers, used by Alembic.
revision = "0004_call_records_direction_and_numbers"
down_revision = "0003_call_exports_call_records"
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover - noop migration
    """Schema updated in 0003; no-op retained for compatibility."""


def downgrade() -> None:  # pragma: no cover - noop migration
    """Schema updated in 0003; no-op retained for compatibility."""
