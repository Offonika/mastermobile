"""Ensure call_id + recording_url combinations are unique."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_call_records_unique_recording_url"
down_revision = "0005_call_records_direction_nullable_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM call_records
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY call_id, recording_url
                           ORDER BY id
                       ) AS row_num
                FROM call_records
                WHERE recording_url IS NOT NULL
            ) duplicates
            WHERE duplicates.row_num > 1
        )
        """
    )

    op.create_index(
        "uq_call_records_call_id_recording_url",
        "call_records",
        ["call_id", "recording_url"],
        unique=True,
        postgresql_where=sa.text("recording_url IS NOT NULL"),
        sqlite_where=sa.text("recording_url IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_call_records_call_id_recording_url",
        table_name="call_records",
    )
