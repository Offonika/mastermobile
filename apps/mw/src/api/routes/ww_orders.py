"""Walking Warehouse order management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.orm import Session

from apps.mw.src.api.dependencies import ProblemDetailException, build_error, provide_request_id
from apps.mw.src.api.schemas import (
    DeliveryLogEntry,
    Error,
    WWOrder,
    WWOrderAssign,
    WWOrderCreate,
    WWOrderStatusChange,
    WWOrderUpdate,
)
from apps.mw.src.db.models import DeliveryLog, DeliveryOrder, DeliveryOrderStatus
from apps.mw.src.db.session import get_session
from apps.mw.src.services.ww_orders import OrderNotFoundError, WWOrderService

router = APIRouter(
    prefix="/api/v1/ww/orders",
    tags=["walking-warehouse"],
    dependencies=[Depends(provide_request_id)],
)


def _serialize_order(order: DeliveryOrder) -> WWOrder:
    return WWOrder(
        id=str(order.order_id),
        external_id=order.external_id,
        status=order.status,
        courier_id=order.courier_id,
        payload=order.payload_json,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def _serialize_log(entry: DeliveryLog) -> DeliveryLogEntry:
    return DeliveryLogEntry(
        id=entry.log_id,
        order_id=str(entry.order_id),
        actor=entry.actor,
        action=entry.action,
        payload=entry.payload_json,
        created_at=entry.created_at,
    )


def _handle_not_found(order_id: UUID, response: Response) -> None:
    problem = build_error(
        status.HTTP_404_NOT_FOUND,
        title="Order not found",
        detail=f"Walking Warehouse order {order_id} was not found.",
        request_id=response.headers.get("X-Request-Id"),
    )
    raise ProblemDetailException(problem)


@router.post(
    "",
    response_model=WWOrder,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"model": Error}},
)
def create_order(
    payload: WWOrderCreate,
    response: Response,
    session: Session = Depends(get_session),
) -> WWOrder:
    service = WWOrderService(session)
    order = service.create_order(
        actor=payload.actor,
        external_id=payload.external_id,
        status=DeliveryOrderStatus(payload.status),
        courier_id=payload.courier_id,
        payload=payload.payload,
    )
    session.commit()
    session.refresh(order)
    response.headers["Location"] = f"/api/v1/ww/orders/{order.order_id}"
    return _serialize_order(order)


@router.put(
    "/{order_id}",
    response_model=WWOrder,
    responses={status.HTTP_404_NOT_FOUND: {"model": Error}},
)
def update_order(
    payload: WWOrderUpdate,
    response: Response,
    order_id: UUID = Path(..., description="Identifier of the Walking Warehouse order."),
    session: Session = Depends(get_session),
) -> WWOrder:
    service = WWOrderService(session)
    try:
        order = service.update_order(
            order_id,
            actor=payload.actor,
            courier_id=payload.courier_id,
            payload=payload.payload,
        )
    except OrderNotFoundError:
        _handle_not_found(order_id, response)
    session.commit()
    session.refresh(order)
    return _serialize_order(order)


@router.post(
    "/{order_id}/assign",
    response_model=WWOrder,
    responses={status.HTTP_404_NOT_FOUND: {"model": Error}},
)
def assign_order(
    payload: WWOrderAssign,
    response: Response,
    order_id: UUID = Path(..., description="Identifier of the Walking Warehouse order."),
    session: Session = Depends(get_session),
) -> WWOrder:
    service = WWOrderService(session)
    try:
        order = service.assign_order(
            order_id,
            actor=payload.actor,
            courier_id=payload.courier_id,
        )
    except OrderNotFoundError:
        _handle_not_found(order_id, response)
    session.commit()
    session.refresh(order)
    return _serialize_order(order)


@router.post(
    "/{order_id}/status",
    response_model=WWOrder,
    responses={status.HTTP_404_NOT_FOUND: {"model": Error}},
)
def change_status(
    payload: WWOrderStatusChange,
    response: Response,
    order_id: UUID = Path(..., description="Identifier of the Walking Warehouse order."),
    session: Session = Depends(get_session),
) -> WWOrder:
    service = WWOrderService(session)
    try:
        order = service.change_status(
            order_id,
            actor=payload.actor,
            status=DeliveryOrderStatus(payload.status),
            reason=payload.reason,
        )
    except OrderNotFoundError:
        _handle_not_found(order_id, response)
    session.commit()
    session.refresh(order)
    return _serialize_order(order)


@router.get(
    "/{order_id}/logs",
    response_model=list[DeliveryLogEntry],
    responses={status.HTTP_404_NOT_FOUND: {"model": Error}},
)
def list_logs(
    response: Response,
    order_id: UUID = Path(..., description="Identifier of the Walking Warehouse order."),
    session: Session = Depends(get_session),
) -> list[DeliveryLogEntry]:
    service = WWOrderService(session)
    try:
        logs = service.list_logs(order_id)
    except OrderNotFoundError:
        _handle_not_found(order_id, response)
    return [_serialize_log(entry) for entry in logs]
