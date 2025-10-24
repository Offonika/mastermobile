"""Ensure delivery log payloads expose the kmp4_exported flag."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_delivery_logs_kmp4_exported"
down_revision = "0008_delivery_tables"
branch_labels = None
depends_on = None

def _payload_type(bind: sa.engine.Connection) -> sa.types.TypeEngine[object]:
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _normalize_flag(value: object) -> bool:
    if isinstance(value, str):
        return value.lower() in {"true", "1", "t", "yes"}
    return bool(value)


def _ensure_payload_dict(payload: object) -> dict[str, object]:
    if isinstance(payload, dict):
        return dict(payload)
    return {}


def _upgrade_rows(connection: sa.engine.Connection) -> None:
    payload_type = _payload_type(connection)
    delivery_logs = sa.table(
        "delivery_logs",
        sa.column("id", sa.BigInteger()),
        sa.column("payload", payload_type),
    )
    rows = connection.execute(
        sa.select(delivery_logs.c.id, delivery_logs.c.payload)
    ).all()
    for row_id, payload in rows:
        normalized = _ensure_payload_dict(payload)
        desired_flag = _normalize_flag(normalized.get("kmp4_exported", False))
        if (
            "kmp4_exported" not in normalized
            or normalized.get("kmp4_exported") != desired_flag
        ):
            normalized["kmp4_exported"] = desired_flag
        if payload != normalized:
            connection.execute(
                sa.update(delivery_logs)
                .where(delivery_logs.c.id == row_id)
                .values(payload=normalized)
            )


def _downgrade_rows(connection: sa.engine.Connection) -> None:
    payload_type = _payload_type(connection)
    delivery_logs = sa.table(
        "delivery_logs",
        sa.column("id", sa.BigInteger()),
        sa.column("payload", payload_type),
    )
    rows = connection.execute(
        sa.select(delivery_logs.c.id, delivery_logs.c.payload)
    ).all()
    for row_id, payload in rows:
        if isinstance(payload, dict) and "kmp4_exported" in payload:
            reduced = dict(payload)
            reduced.pop("kmp4_exported", None)
            new_value = reduced or None
            if new_value != payload:
                connection.execute(
                    sa.update(delivery_logs)
                    .where(delivery_logs.c.id == row_id)
                    .values(payload=new_value)
                )


def upgrade() -> None:
    bind = op.get_bind()
    assert isinstance(bind, sa.engine.Connection)
    _upgrade_rows(bind)
    op.alter_column(
        "delivery_logs",
        "payload",
        existing_type=_payload_type(bind),
        nullable=False,
        server_default=sa.text("'{\"kmp4_exported\": false}'"),
        existing_nullable=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    assert isinstance(bind, sa.engine.Connection)
    op.alter_column(
        "delivery_logs",
        "payload",
        existing_type=_payload_type(bind),
        nullable=True,
        server_default=None,
        existing_nullable=False,
    )
    _downgrade_rows(bind)
