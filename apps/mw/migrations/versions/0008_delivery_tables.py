"""Create delivery tables for couriers and orders."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0008_delivery_tables"
down_revision = "0007_b24_transcripts"
branch_labels = None
depends_on = None


COURIER_STATUS_CHECK = (
    "status IN ('onboarding','active','suspended','inactive')"
)

DELIVERY_ORDER_STATUS_CHECK = (
    "status IN ('new','picking','ready','picked_up','on_route','delivered','cash_returned','done','failed','refused','cancelled')"
)

DELIVERY_ASSIGNMENT_STATUS_CHECK = (
    "status IN ('pending','accepted','declined','in_progress','completed','cancelled')"
)

DELIVERY_LOG_STATUS_CHECK = (
    "status IN ('info','success','warning','error')"
)


def upgrade() -> None:
    op.create_table(
        "couriers",
        sa.Column(
            "courier_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="onboarding"),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(COURIER_STATUS_CHECK, name="chk_couriers_status"),
        sa.CheckConstraint(
            "length(trim(phone)) > 0", name="chk_couriers_phone_not_blank"
        ),
    )

    op.create_index("idx_couriers_status", "couriers", ["status"])

    op.create_table(
        "delivery_orders",
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="new"),
        sa.Column("courier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "delivery_price",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cod_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "currency_code",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'RUB'"),
        ),
        sa.Column("expected_delivery_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["courier_id"], ["couriers.courier_id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            DELIVERY_ORDER_STATUS_CHECK, name="chk_delivery_orders_status"
        ),
        sa.CheckConstraint(
            "delivery_price >= 0",
            name="chk_delivery_orders_delivery_price_non_negative",
        ),
        sa.CheckConstraint(
            "cod_amount >= 0",
            name="chk_delivery_orders_cod_amount_non_negative",
        ),
    )

    op.create_index(
        "idx_delivery_orders_status_active",
        "delivery_orders",
        ["status"],
        postgresql_where=sa.text(
            "status IN ('new','picking','ready','picked_up','on_route','delivered')"
        ),
    )
    op.create_index(
        "idx_delivery_orders_courier_status",
        "delivery_orders",
        ["courier_id", "status"],
    )
    op.create_index(
        "uq_delivery_orders_external_id",
        "delivery_orders",
        ["external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "delivery_assignments",
        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("courier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.Text(), nullable=False, server_default="pending"
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "assigned_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("accepted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["delivery_orders.order_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["courier_id"], ["couriers.courier_id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            DELIVERY_ASSIGNMENT_STATUS_CHECK,
            name="chk_delivery_assignments_status",
        ),
    )

    op.create_index(
        "idx_delivery_assignments_order_status",
        "delivery_assignments",
        ["order_id", "status"],
    )
    op.create_index(
        "uq_delivery_assignments_active",
        "delivery_assignments",
        ["order_id", "courier_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending','accepted','in_progress')"
        ),
    )

    op.create_table(
        "delivery_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("courier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="info"),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["delivery_orders.order_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["delivery_assignments.assignment_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["courier_id"], ["couriers.courier_id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            DELIVERY_LOG_STATUS_CHECK,
            name="chk_delivery_logs_status",
        ),
    )

    op.create_index(
        "idx_delivery_logs_order_created",
        "delivery_logs",
        ["order_id", "created_at"],
    )
    op.create_index("idx_delivery_logs_status", "delivery_logs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_delivery_logs_status", table_name="delivery_logs")
    op.drop_index(
        "idx_delivery_logs_order_created", table_name="delivery_logs"
    )
    op.drop_table("delivery_logs")

    op.drop_index(
        "uq_delivery_assignments_active", table_name="delivery_assignments"
    )
    op.drop_index(
        "idx_delivery_assignments_order_status",
        table_name="delivery_assignments",
    )
    op.drop_table("delivery_assignments")

    op.drop_index(
        "uq_delivery_orders_external_id", table_name="delivery_orders"
    )
    op.drop_index(
        "idx_delivery_orders_courier_status", table_name="delivery_orders"
    )
    op.drop_index(
        "idx_delivery_orders_status_active", table_name="delivery_orders"
    )
    op.drop_table("delivery_orders")

    op.drop_index("idx_couriers_status", table_name="couriers")
    op.drop_table("couriers")
