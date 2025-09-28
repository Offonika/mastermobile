"""Repository helpers for :class:`DeliveryAssignment`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.mw.src.db.models import (
    DeliveryAssignment,
    DeliveryAssignmentStatus,
)


class DeliveryAssignmentRepository:
    """CRUD helpers for delivery assignments."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        order_id: UUID,
        courier_id: UUID,
        status: DeliveryAssignmentStatus = DeliveryAssignmentStatus.PENDING,
        notes: str | None = None,
    ) -> DeliveryAssignment:
        assignment = DeliveryAssignment(
            order_id=order_id,
            courier_id=courier_id,
            status=status,
            notes=notes,
        )
        self._session.add(assignment)
        self._session.flush()
        return assignment

    def get(self, assignment_id: UUID) -> DeliveryAssignment | None:
        statement: Select[tuple[DeliveryAssignment]] = select(
            DeliveryAssignment
        ).where(DeliveryAssignment.assignment_id == assignment_id)
        return self._session.scalar(statement)

    def list_active_for_order(self, order_id: UUID) -> list[DeliveryAssignment]:
        statement = (
            select(DeliveryAssignment)
            .where(
                DeliveryAssignment.order_id == order_id,
                DeliveryAssignment.status.in_(
                    [
                        DeliveryAssignmentStatus.PENDING,
                        DeliveryAssignmentStatus.ACCEPTED,
                        DeliveryAssignmentStatus.IN_PROGRESS,
                    ]
                ),
            )
            .order_by(DeliveryAssignment.assigned_at)
        )
        return list(self._session.scalars(statement).all())

    def update_status(
        self,
        assignment: DeliveryAssignment,
        status: DeliveryAssignmentStatus,
        *,
        accepted_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> DeliveryAssignment:
        assignment.status = status
        if accepted_at is not None:
            assignment.accepted_at = accepted_at
        if completed_at is not None:
            assignment.completed_at = completed_at
        self._session.flush()
        return assignment

    def reassign(
        self,
        assignment: DeliveryAssignment,
        *,
        courier_id: UUID,
        notes: str | None = None,
    ) -> DeliveryAssignment:
        assignment.courier_id = courier_id
        if notes is not None:
            assignment.notes = notes
        self._session.flush()
        return assignment

    def delete(self, assignment: DeliveryAssignment) -> None:
        self._session.delete(assignment)
        self._session.flush()
