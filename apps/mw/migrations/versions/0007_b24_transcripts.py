"""Create table for Bitrix24 transcripts."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

# revision identifiers, used by Alembic.
revision = "0007_b24_transcripts"
down_revision = "0006_call_records_unique_recording_url"
branch_labels = None
depends_on = ("0006_call_records_add_employee_text_preview",)


def upgrade() -> None:
    op.create_table(
        "b24_transcripts",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True, autoincrement=True),
        sa.Column(
            "call_record_id",
            sa.BigInteger().with_variant(sa.Integer, "sqlite"),
            sa.ForeignKey("call_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text_full", sa.Text(), nullable=False),
        sa.Column("text_normalized", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB().with_variant(SQLiteJSON(), "sqlite"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_b24_transcripts_call_record_id",
        "b24_transcripts",
        ["call_record_id"],
        unique=True,
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX ix_b24_transcripts_text_full_fts
            ON b24_transcripts
            USING GIN (to_tsvector('russian', text_full))
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_b24_transcripts_text_full_fts")

    op.drop_index("uq_b24_transcripts_call_record_id", table_name="b24_transcripts")
    op.drop_table("b24_transcripts")
