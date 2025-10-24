"""Repository helpers for :class:`~apps.mw.src.db.models.Courier`."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from apps.mw.src.db.models import Courier, CourierStatus


class CourierRepository:
    """CRUD facade around the :class:`Courier` ORM model."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        external_id: str | None,
        full_name: str,
        phone: str,
        email: str | None = None,
        status: CourierStatus = CourierStatus.ONBOARDING,
        metadata: dict[str, object] | None = None,
    ) -> Courier:
        courier = Courier(
            external_id=external_id,
            full_name=full_name,
            phone=phone,
            email=email,
            status=status,
            metadata_json=metadata,
        )
        self._session.add(courier)
        self._session.flush()
        return courier

    def get(self, courier_id: UUID) -> Courier | None:
        statement: Select[tuple[Courier]] = select(Courier).where(
            Courier.courier_id == courier_id
        )
        return self._session.scalar(statement)

    def list_by_status(self, *statuses: CourierStatus) -> list[Courier]:
        if not statuses:
            statement: Select[tuple[Courier]] = select(Courier).order_by(
                Courier.full_name
            )
        else:
            statement = select(Courier).where(Courier.status.in_(statuses)).order_by(
                Courier.full_name
            )
        return list(self._session.scalars(statement).all())

    def update_status(self, courier: Courier, status: CourierStatus) -> Courier:
        courier.status = status
        self._session.flush()
        return courier

    def update_contacts(
        self,
        courier: Courier,
        *,
        phone: str | None = None,
        email: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Courier:
        if phone is not None:
            courier.phone = phone
        if email is not None:
            courier.email = email
        if metadata is not None:
            courier.metadata_json = metadata
        self._session.flush()
        return courier

    def delete(self, courier: Courier) -> None:
        self._session.delete(courier)
        self._session.flush()

    def upsert_many(self, couriers: Iterable[Courier]) -> None:
        for courier in couriers:
            self._session.merge(courier)
        self._session.flush()
