"""Walking Warehouse API endpoints."""
from __future__ import annotations

from uuid import uuid4
from typing import Any, Iterable

from fastapi import APIRouter, Depends, Path, Query, Response, status

from apps.mw.src.api.dependencies import (
    ProblemDetailException,
    build_error,
    enforce_idempotency_key,
    IdempotencyContext,
    provide_request_id,
)
from apps.mw.src.api.schemas import (
    Courier,
    CourierCreate,
    CouriersResponse,
    Error,
    Order,
    OrderAssign,
    OrderCreate,
    OrderCreateItem,
    OrderListResponse,
    OrderStatusUpdate,
    OrderUpdate,
    WWOrderStatus,
)
from apps.mw.src.integrations.ww import (
    CourierAlreadyExistsError,
    CourierNotFoundError,
    InvalidOrderStatusTransitionError,
    OrderAlreadyExistsError,
    OrderItemRecord,
    OrderNotFoundError,
    OrderStateMachine,
    WalkingWarehouseCourierRepository,
    WalkingWarehouseOrderRepository,
)

router = APIRouter(
    prefix="/api/v1/ww",
    tags=["walking-warehouse"],
    dependencies=[Depends(provide_request_id)],
)

_courier_repository = WalkingWarehouseCourierRepository()
_order_repository = WalkingWarehouseOrderRepository()


def get_courier_repository() -> WalkingWarehouseCourierRepository:
    """Dependency providing the courier repository."""

    return _courier_repository


def get_order_repository() -> WalkingWarehouseOrderRepository:
    """Dependency providing the order repository."""

    return _order_repository


def _serialize_courier(record: object) -> Courier:
    return Courier.model_validate(record)


def _serialize_order(record: object) -> Order:
    return Order.model_validate(record)


def _serialize_items(items: Iterable[OrderCreateItem | dict[str, Any]]) -> list[OrderItemRecord]:
    serialised: list[OrderItemRecord] = []
    for item in items:
        if isinstance(item, OrderCreateItem):
            payload = item
        else:
            payload = OrderCreateItem.model_validate(item)
        serialised.append(
            OrderItemRecord(
                sku=payload.sku,
                name=payload.name,
                qty=payload.qty,
                price=payload.price,
            )
        )
    return serialised


@router.post(
    "/couriers",
    response_model=Courier,
    status_code=status.HTTP_201_CREATED,
    summary="Create courier",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": Error, "description": "Missing principal."},
        status.HTTP_403_FORBIDDEN: {"model": Error, "description": "Forbidden."},
        status.HTTP_409_CONFLICT: {"model": Error, "description": "Courier already exists."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": Error, "description": "Validation error."},
    },
)
async def create_courier(
    payload: CourierCreate,
    response: Response,
    repository: WalkingWarehouseCourierRepository = Depends(get_courier_repository),
    _idempotency: IdempotencyContext = Depends(enforce_idempotency_key),
) -> Courier:
    """Register a new courier in the Walking Warehouse registry."""

    try:
        record = repository.create(
            courier_id=payload.id,
            display_name=payload.display_name,
            phone=payload.phone,
            is_active=payload.is_active,
        )
    except CourierAlreadyExistsError as exc:
        error = build_error(
            status.HTTP_409_CONFLICT,
            title="Courier already exists",
            detail=f"Courier {payload.id} already exists.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc

    response.headers["Location"] = f"/api/v1/ww/couriers/{record.id}"
    return _serialize_courier(record)


@router.get(
    "/couriers",
    response_model=CouriersResponse,
    summary="List couriers",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": Error, "description": "Missing principal."},
        status.HTTP_403_FORBIDDEN: {"model": Error, "description": "Forbidden."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": Error, "description": "Validation error."},
    },
)
def list_couriers(
    repository: WalkingWarehouseCourierRepository = Depends(get_courier_repository),
    q: str | None = Query(
        default=None,
        description="Case-insensitive search across courier id, name and phone.",
        min_length=1,
    ),
) -> CouriersResponse:
    """Retrieve couriers optionally filtered by a search query."""

    records = repository.list(q=q)
    return CouriersResponse(items=[_serialize_courier(record) for record in records])


@router.post(
    "/orders",
    response_model=Order,
    status_code=status.HTTP_201_CREATED,
    summary="Create order",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": Error, "description": "Missing principal."},
        status.HTTP_403_FORBIDDEN: {"model": Error, "description": "Forbidden."},
        status.HTTP_404_NOT_FOUND: {"model": Error, "description": "Related courier not found."},
        status.HTTP_409_CONFLICT: {"model": Error, "description": "Order already exists."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": Error, "description": "Validation error."},
    },
)
async def create_order(
    payload: OrderCreate,
    response: Response,
    order_repository: WalkingWarehouseOrderRepository = Depends(get_order_repository),
    courier_repository: WalkingWarehouseCourierRepository = Depends(get_courier_repository),
    idempotency: IdempotencyContext = Depends(enforce_idempotency_key),
) -> Order:
    """Create a new instant order."""

    if idempotency.is_replay:
        cached_headers = idempotency.get_replay_headers()
        for name, value in cached_headers.items():
            response.headers[name] = value
        response.status_code = status.HTTP_200_OK
        cached_payload = idempotency.get_replay_payload()
        if cached_payload is None:
            raise ProblemDetailException(
                build_error(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    title="Idempotency replay failed",
                    detail="Cached response payload is missing.",
                    request_id=response.headers.get("X-Request-Id"),
                )
            )
        return cached_payload  # type: ignore[return-value]

    if payload.courier_id is not None:
        try:
            courier_repository.get(payload.courier_id)
        except CourierNotFoundError as exc:
            error = build_error(
                status.HTTP_404_NOT_FOUND,
                title="Courier not found",
                detail=f"Courier {payload.courier_id} was not found.",
                request_id=response.headers.get("X-Request-Id"),
            )
            raise ProblemDetailException(error) from exc

    order_id = payload.id or str(uuid4())
    items = _serialize_items(payload.items)

    try:
        record = order_repository.create(
            order_id=order_id,
            title=payload.title,
            customer_name=payload.customer_name,
            status=payload.status.value if isinstance(payload.status, WWOrderStatus) else str(payload.status),
            courier_id=payload.courier_id,
            currency_code=payload.currency_code,
            total_amount=payload.total_amount,
            notes=payload.notes,
            items=items,
        )
    except OrderAlreadyExistsError as exc:
        error = build_error(
            status.HTTP_409_CONFLICT,
            title="Order already exists",
            detail=f"Order {order_id} already exists.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc

    response.headers["Location"] = f"/api/v1/ww/orders/{record.id}"
    serialized = _serialize_order(record)
    idempotency.store_response(
        status_code=status.HTTP_201_CREATED,
        payload=serialized,
        headers={"Location": response.headers["Location"]},
    )
    return serialized


@router.get(
    "/orders",
    response_model=OrderListResponse,
    summary="List orders",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": Error, "description": "Missing principal."},
        status.HTTP_403_FORBIDDEN: {"model": Error, "description": "Forbidden."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": Error, "description": "Validation error."},
    },
)
def list_orders(
    order_repository: WalkingWarehouseOrderRepository = Depends(get_order_repository),
    status_filter: list[WWOrderStatus] | None = Query(
        default=None,
        alias="status",
        description="Filter by order status; multiple values allowed.",
    ),
    q: str | None = Query(
        default=None,
        description="Case-insensitive search across id, title and customer name.",
        min_length=1,
    ),
) -> OrderListResponse:
    """List orders optionally filtered by status and search query."""

    statuses = None
    if status_filter is not None:
        statuses = [status.value for status in status_filter]

    records = order_repository.list(statuses=statuses, q=q)
    items = [_serialize_order(record) for record in records]
    return OrderListResponse(items=items, total=len(items))


@router.patch(
    "/orders/{order_id}",
    response_model=Order,
    summary="Update order",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": Error, "description": "Missing principal."},
        status.HTTP_403_FORBIDDEN: {"model": Error, "description": "Forbidden."},
        status.HTTP_404_NOT_FOUND: {"model": Error, "description": "Order not found."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": Error, "description": "Validation error."},
    },
)
async def update_order(
    payload: OrderUpdate,
    response: Response,
    order_id: str = Path(..., description="Identifier of the order to update."),
    order_repository: WalkingWarehouseOrderRepository = Depends(get_order_repository),
    _idempotency: IdempotencyContext = Depends(enforce_idempotency_key),
) -> Order:
    """Apply partial updates to an order."""

    update_data = payload.model_dump(exclude_unset=True)
    items_payload = update_data.pop("items", None)
    items = _serialize_items(items_payload) if items_payload is not None else None

    try:
        record = order_repository.update(
            order_id,
            title=update_data.get("title"),
            customer_name=update_data.get("customer_name"),
            notes=update_data.get("notes"),
            items=items,
            total_amount=update_data.get("total_amount"),
            currency_code=update_data.get("currency_code"),
        )
    except OrderNotFoundError as exc:
        error = build_error(
            status.HTTP_404_NOT_FOUND,
            title="Order not found",
            detail=f"Order {order_id} was not found.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc

    return _serialize_order(record)


@router.post(
    "/orders/{order_id}/assign",
    response_model=Order,
    summary="Assign courier",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": Error, "description": "Missing principal."},
        status.HTTP_403_FORBIDDEN: {"model": Error, "description": "Forbidden."},
        status.HTTP_404_NOT_FOUND: {"model": Error, "description": "Order or courier not found."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": Error, "description": "Validation error."},
    },
)
async def assign_order(
    payload: OrderAssign,
    response: Response,
    order_id: str = Path(..., description="Identifier of the order to update."),
    order_repository: WalkingWarehouseOrderRepository = Depends(get_order_repository),
    courier_repository: WalkingWarehouseCourierRepository = Depends(get_courier_repository),
    _idempotency: IdempotencyContext = Depends(enforce_idempotency_key),
) -> Order:
    """Assign or unassign a courier for an order."""

    if payload.courier_id is not None:
        try:
            courier_repository.get(payload.courier_id)
        except CourierNotFoundError as exc:
            error = build_error(
                status.HTTP_404_NOT_FOUND,
                title="Courier not found",
                detail=f"Courier {payload.courier_id} was not found.",
                request_id=response.headers.get("X-Request-Id"),
            )
            raise ProblemDetailException(error) from exc

    try:
        record = order_repository.get(order_id)
    except OrderNotFoundError as exc:
        error = build_error(
            status.HTTP_404_NOT_FOUND,
            title="Order not found",
            detail=f"Order {order_id} was not found.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc

    machine = OrderStateMachine.from_raw(record.status)

    def _transition_error(exc: InvalidOrderStatusTransitionError) -> ProblemDetailException:
        detail = (
            f"Cannot transition order {order_id} from {exc.current} to {exc.new}."
        )
        error = build_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Invalid order status transition",
            detail=detail,
            request_id=response.headers.get("X-Request-Id"),
        )
        return ProblemDetailException(error)

    if payload.courier_id is not None:
        try:
            machine.ensure_transition(WWOrderStatus.ASSIGNED)
        except InvalidOrderStatusTransitionError as exc:
            raise _transition_error(exc) from exc

        order_repository.assign_courier(order_id, payload.courier_id)
        record = order_repository.update_status(order_id, machine.current.value)
        return _serialize_order(record)

    if payload.decline and record.courier_id is None:
        error = build_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Invalid assignment state",
            detail="Cannot decline an order without an assigned courier.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error)

    if payload.decline:
        try:
            machine.ensure_transition(WWOrderStatus.DECLINED)
        except InvalidOrderStatusTransitionError as exc:
            raise _transition_error(exc) from exc
        order_repository.update_status(order_id, machine.current.value)

    target_status = WWOrderStatus.NEW
    try:
        machine.ensure_transition(target_status)
    except InvalidOrderStatusTransitionError as exc:
        raise _transition_error(exc) from exc

    order_repository.assign_courier(order_id, None)
    record = order_repository.update_status(order_id, machine.current.value)
    return _serialize_order(record)


@router.post(
    "/orders/{order_id}/status",
    response_model=Order,
    summary="Update order status",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": Error, "description": "Missing principal."},
        status.HTTP_403_FORBIDDEN: {"model": Error, "description": "Forbidden."},
        status.HTTP_404_NOT_FOUND: {"model": Error, "description": "Order not found."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": Error, "description": "Validation error."},
    },
)
async def update_order_status(
    payload: OrderStatusUpdate,
    response: Response,
    order_id: str = Path(..., description="Identifier of the order to update."),
    order_repository: WalkingWarehouseOrderRepository = Depends(get_order_repository),
    _idempotency: IdempotencyContext = Depends(enforce_idempotency_key),
) -> Order:
    """Transition an order to a new status."""

    try:
        record = order_repository.get(order_id)
    except OrderNotFoundError as exc:
        error = build_error(
            status.HTTP_404_NOT_FOUND,
            title="Order not found",
            detail=f"Order {order_id} was not found.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc

    new_status = payload.status if isinstance(payload.status, WWOrderStatus) else WWOrderStatus(payload.status)
    machine = OrderStateMachine.from_raw(record.status)

    try:
        machine.ensure_transition(new_status)
    except InvalidOrderStatusTransitionError as exc:
        error = build_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Invalid order status transition",
            detail=f"Cannot transition order {order_id} from {exc.current} to {exc.new}.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc

    record = order_repository.update_status(order_id, machine.current.value)
    return _serialize_order(record)
