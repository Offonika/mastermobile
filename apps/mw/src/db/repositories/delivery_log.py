"""Repositories handling persistence of Walking Warehouse delivery logs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.mw.src.db.models import DeliveryLog


class DeliveryLogRepository:
    """Helper class to append and query delivery log entries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        order_id: UUID,
        actor: str,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> DeliveryLog:
        """Persist a log entry for a Walking Warehouse order."""

        entry = DeliveryLog(
            order_id=order_id,
            actor=actor,
            action=action,
            payload_json=payload,
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    def list_for_order(self, order_id: UUID) -> list[DeliveryLog]:
        """Return log entries associated with the specified order."""

        statement: Select[tuple[DeliveryLog]] = (
            select(DeliveryLog)
            .where(DeliveryLog.order_id == order_id)
            .order_by(DeliveryLog.created_at.asc(), DeliveryLog.log_id.asc())
        )
        return list(self._session.scalars(statement))
