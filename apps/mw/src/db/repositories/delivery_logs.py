"""Repository helpers for :class:`DeliveryLog`."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.mw.src.db.models import DeliveryLog, DeliveryLogStatus


class DeliveryLogRepository:
    """CRUD helpers for delivery workflow logs."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        order_id: UUID,
        status: DeliveryLogStatus,
        event_type: str,
        assignment_id: UUID | None = None,
        courier_id: UUID | None = None,
        message: str | None = None,
        payload: dict[str, object] | None = None,
        kmp4_exported: bool = False,
    ) -> DeliveryLog:
        log_entry = DeliveryLog(
            order_id=order_id,
            assignment_id=assignment_id,
            courier_id=courier_id,
            status=status,
            event_type=event_type,
            message=message,
            payload=DeliveryLog.normalize_payload(
                payload, kmp4_exported=kmp4_exported
            ),
        )
        self._session.add(log_entry)
        self._session.flush()
        return log_entry

    def list_for_order(self, order_id: UUID) -> list[DeliveryLog]:
        statement: Select[tuple[DeliveryLog]] = (
            select(DeliveryLog)
            .where(DeliveryLog.order_id == order_id)
            .order_by(DeliveryLog.created_at)
        )
        return list(self._session.scalars(statement).all())

    def delete(self, log_entry: DeliveryLog) -> None:
        self._session.delete(log_entry)
        self._session.flush()
