"""Business logic helpers for Walking Warehouse orders."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from apps.mw.src.db.models import DeliveryLog, DeliveryOrder, DeliveryOrderStatus
from apps.mw.src.db.repositories.delivery_log import DeliveryLogRepository


class OrderNotFoundError(LookupError):
    """Raised when a requested order cannot be located in the database."""


class WWOrderService:
    """Encapsulates Walking Warehouse order workflows."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._log_repo = DeliveryLogRepository(session)

    def create_order(
        self,
        *,
        actor: str,
        external_id: str,
        status: DeliveryOrderStatus = DeliveryOrderStatus.DRAFT,
        courier_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> DeliveryOrder:
        """Persist a new Walking Warehouse order and log the creation."""

        order = DeliveryOrder(
            external_id=external_id,
            status=status,
            courier_id=courier_id,
            payload_json=payload,
        )
        self._session.add(order)
        self._session.flush()
        self._log_repo.record(
            order_id=order.order_id,
            actor=actor,
            action="order_created",
            payload={
                "external_id": external_id,
                "status": status.value,
                "courier_id": courier_id,
                "payload": payload,
            },
        )
        return order

    def update_order(
        self,
        order_id: UUID,
        *,
        actor: str,
        courier_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> DeliveryOrder:
        """Update mutable fields on an existing order and log the change."""

        order = self._get_order(order_id)
        changes: dict[str, Any] = {}

        if courier_id is not None:
            order.courier_id = courier_id
            changes["courier_id"] = courier_id
        if payload is not None:
            order.payload_json = payload
            changes["payload"] = payload

        self._session.flush()
        self._log_repo.record(
            order_id=order.order_id,
            actor=actor,
            action="order_updated",
            payload=changes or None,
        )
        return order

    def assign_order(
        self,
        order_id: UUID,
        *,
        actor: str,
        courier_id: str,
    ) -> DeliveryOrder:
        """Assign a courier to an order and log the operation."""

        order = self._get_order(order_id)
        order.courier_id = courier_id
        self._session.flush()
        self._log_repo.record(
            order_id=order.order_id,
            actor=actor,
            action="order_assigned",
            payload={"courier_id": courier_id},
        )
        return order

    def change_status(
        self,
        order_id: UUID,
        *,
        actor: str,
        status: DeliveryOrderStatus,
        reason: str | None = None,
    ) -> DeliveryOrder:
        """Update the status of the order and log the transition."""

        order = self._get_order(order_id)
        order.status = status
        self._session.flush()
        payload: dict[str, Any] = {"status": status.value}
        if reason:
            payload["reason"] = reason
        self._log_repo.record(
            order_id=order.order_id,
            actor=actor,
            action="status_changed",
            payload=payload,
        )
        return order

    def list_logs(self, order_id: UUID) -> list[DeliveryLog]:
        """Proxy to the repository for retrieving order logs."""

        self._ensure_exists(order_id)
        return self._log_repo.list_for_order(order_id)

    def _get_order(self, order_id: UUID) -> DeliveryOrder:
        order = self._session.get(DeliveryOrder, order_id)
        if order is None:
            raise OrderNotFoundError(str(order_id))
        return order

    def _ensure_exists(self, order_id: UUID) -> None:
        if self._session.get(DeliveryOrder, order_id) is None:
            raise OrderNotFoundError(str(order_id))
