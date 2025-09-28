"""Walking Warehouse API endpoints."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Iterable, Literal
from uuid import uuid4

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
    DeliveryReportResponse,
    DeliveryReportRow,
    DeliveryReportTotals,
    KMP4ExportResponse,
    KMP4Order,
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
from apps.mw.src.integrations.ww.kmp4_export import KMP4ExportError, KMP4OrderPayload
from apps.mw.src.observability.metrics import (
    WW_ORDER_STATUS_TRANSITIONS_TOTAL,
    WWExportTracker,
)
from apps.mw.src.services.ww_reports import DeliveryReport, WWReportService

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


def get_report_service(
    order_repository: WalkingWarehouseOrderRepository = Depends(get_order_repository),
    courier_repository: WalkingWarehouseCourierRepository = Depends(get_courier_repository),
) -> WWReportService:
    """Dependency constructing the Walking Warehouse report service."""

    return WWReportService(order_repository, courier_repository)


def _serialize_courier(record: object) -> Courier:
    return Courier.model_validate(record)


def _serialize_order(record: object) -> Order:
    return Order.model_validate(record)


def _render_delivery_report_csv(report: DeliveryReport) -> str:
    """Render the delivery report into a UTF-8 CSV string with totals."""

    headers = [
        "order_id",
        "courier_id",
        "courier_name",
        "status",
        "title",
        "customer_name",
        "total_amount",
        "currency_code",
        "created_at",
        "updated_at",
        "duration_min",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in report.rows:
        writer.writerow(
            {
                "order_id": row.order_id,
                "courier_id": row.courier_id or "",
                "courier_name": row.courier_name or "",
                "status": row.status,
                "title": row.title,
                "customer_name": row.customer_name,
                "total_amount": str(row.total_amount),
                "currency_code": row.currency_code,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "duration_min": f"{row.duration_min:.2f}",
            }
        )

    writer.writerow(
        {
            "order_id": "TOTALS",
            "courier_id": "",
            "courier_name": "",
            "status": "",
            "title": "",
            "customer_name": "",
            "total_amount": str(report.total_amount),
            "currency_code": "",
            "created_at": "",
            "updated_at": "",
            "duration_min": f"{report.total_duration_min:.2f}",
        }
    )

    return "\ufeff" + buffer.getvalue()


def _as_delivery_response(report: DeliveryReport) -> DeliveryReportResponse:
    """Convert a delivery report aggregate into the API schema."""

    items = [DeliveryReportRow.model_validate(row) for row in report.rows]
    totals = DeliveryReportTotals(
        total_orders=report.total_orders,
        total_amount=report.total_amount,
        total_duration_min=report.total_duration_min,
    )
    return DeliveryReportResponse(items=items, totals=totals)


def _as_kmp4_response(payloads: list[KMP4OrderPayload]) -> KMP4ExportResponse:
    """Convert serialized KMP4 orders into the API schema."""

    orders = [KMP4Order.model_validate(payload) for payload in payloads]
    return KMP4ExportResponse(items=orders, total=len(orders))


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

    tracker = WWExportTracker("order_create")

    if payload.courier_id is not None:
        try:
            courier_repository.get(payload.courier_id)
        except CourierNotFoundError as exc:
            tracker.failure("courier_not_found")
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
        tracker.failure("duplicate_order")
        error = build_error(
            status.HTTP_409_CONFLICT,
            title="Order already exists",
            detail=f"Order {order_id} already exists.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc
    except Exception:
        tracker.failure("unexpected_error")
        raise

    tracker.success()
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

    tracker = WWExportTracker("order_update")
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
        tracker.failure("order_not_found")
        error = build_error(
            status.HTTP_404_NOT_FOUND,
            title="Order not found",
            detail=f"Order {order_id} was not found.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc
    except Exception:
        tracker.failure("unexpected_error")
        raise

    tracker.success()
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

    tracker = WWExportTracker("order_assign")
    if payload.courier_id is not None:
        try:
            courier_repository.get(payload.courier_id)
        except CourierNotFoundError as exc:
            tracker.failure("courier_not_found")
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
        tracker.failure("order_not_found")
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
        WW_ORDER_STATUS_TRANSITIONS_TOTAL.labels(
            exc.current.value,
            exc.new.value,
            "failure",
        ).inc()
        tracker.failure("invalid_transition")
        error = build_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Invalid order status transition",
            detail=detail,
            request_id=response.headers.get("X-Request-Id"),
        )
        return ProblemDetailException(error)

    if payload.courier_id is not None:
        previous_status = machine.current.value
        try:
            machine.ensure_transition(WWOrderStatus.ASSIGNED)
        except InvalidOrderStatusTransitionError as exc:
            raise _transition_error(exc) from exc

        WW_ORDER_STATUS_TRANSITIONS_TOTAL.labels(
            previous_status,
            machine.current.value,
            "success",
        ).inc()
        order_repository.assign_courier(order_id, payload.courier_id)
        record = order_repository.update_status(order_id, machine.current.value)
        tracker.success()
        return _serialize_order(record)

    if payload.decline and record.courier_id is None:
        tracker.failure("invalid_assignment_state")
        error = build_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Invalid assignment state",
            detail="Cannot decline an order without an assigned courier.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error)

    if payload.decline:
        previous_status = machine.current.value
        try:
            machine.ensure_transition(WWOrderStatus.DECLINED)
        except InvalidOrderStatusTransitionError as exc:
            raise _transition_error(exc) from exc
        WW_ORDER_STATUS_TRANSITIONS_TOTAL.labels(
            previous_status,
            machine.current.value,
            "success",
        ).inc()
        record = order_repository.update_status(order_id, machine.current.value)

    target_status = WWOrderStatus.NEW
    previous_status = machine.current.value
    try:
        machine.ensure_transition(target_status)
    except InvalidOrderStatusTransitionError as exc:
        raise _transition_error(exc) from exc

    WW_ORDER_STATUS_TRANSITIONS_TOTAL.labels(
        previous_status,
        machine.current.value,
        "success",
    ).inc()
    order_repository.assign_courier(order_id, None)
    record = order_repository.update_status(order_id, machine.current.value)
    tracker.success()
    return _serialize_order(record)


@router.get(
    "/report/deliveries",
    response_model=DeliveryReportResponse,
    summary="Walking Warehouse delivery report",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": Error, "description": "Missing principal."},
        status.HTTP_403_FORBIDDEN: {"model": Error, "description": "Forbidden."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": Error, "description": "Validation error."},
    },
)
def get_delivery_report(
    response: Response,
    report_service: WWReportService = Depends(get_report_service),
    status_filter: list[WWOrderStatus] | None = Query(
        default=None,
        alias="status",
        description="Filter by order status; multiple values allowed.",
    ),
    courier_id: str | None = Query(
        default=None,
        description="Filter deliveries handled by a specific courier.",
        min_length=1,
    ),
    created_from: datetime | None = Query(
        default=None,
        description="Return deliveries created on or after the specified timestamp.",
    ),
    created_to: datetime | None = Query(
        default=None,
        description="Return deliveries created on or before the specified timestamp.",
    ),
    output_format: Literal["json", "csv"] = Query(
        default="json",
        alias="format",
        description="Set to `csv` to receive the response as UTF-8 CSV.",
    ),
) -> DeliveryReportResponse | Response:
    """Return aggregated delivery metrics optionally rendered as CSV."""

    tracker = WWExportTracker("deliveries_report")
    statuses = [status.value for status in status_filter] if status_filter else None

    if created_from and created_to and created_from > created_to:
        tracker.failure("invalid_date_range")
        error = build_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Invalid date range",
            detail="`created_from` must be earlier than or equal to `created_to`.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error)

    report = report_service.generate_delivery_report(
        statuses=statuses,
        courier_id=courier_id,
        created_from=created_from,
        created_to=created_to,
    )

    if output_format == "csv":
        payload = _render_delivery_report_csv(report)
        tracker.success()
        csv_response = Response(content=payload, media_type="text/csv; charset=utf-8")
        csv_response.headers["Content-Disposition"] = "attachment; filename=deliveries.csv"
        request_id = response.headers.get("X-Request-Id")
        if request_id:
            csv_response.headers["X-Request-Id"] = request_id
        return csv_response

    tracker.success()
    return _as_delivery_response(report)


@router.get(
    "/export/kmp4",
    response_model=KMP4ExportResponse,
    summary="Walking Warehouse KMP4 export",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": Error, "description": "Missing principal."},
        status.HTTP_403_FORBIDDEN: {"model": Error, "description": "Forbidden."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": Error, "description": "Validation error."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": Error,
            "description": "Unexpected export serialization error.",
        },
    },
)
def export_kmp4(
    response: Response,
    report_service: WWReportService = Depends(get_report_service),
    status_filter: list[WWOrderStatus] | None = Query(
        default=None,
        alias="status",
        description="Filter by order status; multiple values allowed.",
    ),
    courier_id: str | None = Query(
        default=None,
        description="Filter deliveries handled by a specific courier.",
        min_length=1,
    ),
    created_from: datetime | None = Query(
        default=None,
        description="Return deliveries created on or after the specified timestamp.",
    ),
    created_to: datetime | None = Query(
        default=None,
        description="Return deliveries created on or before the specified timestamp.",
    ),
) -> KMP4ExportResponse:
    """Serialize deliveries into the structure expected by the KMP4 upload."""

    tracker = WWExportTracker("kmp4_export")
    statuses = [status.value for status in status_filter] if status_filter else None

    if created_from and created_to and created_from > created_to:
        tracker.failure("invalid_date_range")
        error = build_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Invalid date range",
            detail="`created_from` must be earlier than or equal to `created_to`.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error)

    try:
        payloads = report_service.build_kmp4_export(
            statuses=statuses,
            courier_id=courier_id,
            created_from=created_from,
            created_to=created_to,
        )
    except KMP4ExportError as exc:
        tracker.failure("serialization_error")
        error = build_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="KMP4 export failed",
            detail=str(exc),
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc

    tracker.success()
    return _as_kmp4_response(payloads)


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

    tracker = WWExportTracker("order_status_update")
    try:
        record = order_repository.get(order_id)
    except OrderNotFoundError as exc:
        tracker.failure("order_not_found")
        error = build_error(
            status.HTTP_404_NOT_FOUND,
            title="Order not found",
            detail=f"Order {order_id} was not found.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc

    new_status = payload.status if isinstance(payload.status, WWOrderStatus) else WWOrderStatus(payload.status)
    machine = OrderStateMachine.from_raw(record.status)

    previous_status = machine.current.value
    try:
        machine.ensure_transition(new_status)
    except InvalidOrderStatusTransitionError as exc:
        WW_ORDER_STATUS_TRANSITIONS_TOTAL.labels(
            exc.current.value,
            exc.new.value,
            "failure",
        ).inc()
        tracker.failure("invalid_transition")
        error = build_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Invalid order status transition",
            detail=f"Cannot transition order {order_id} from {exc.current} to {exc.new}.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error) from exc

    WW_ORDER_STATUS_TRANSITIONS_TOTAL.labels(
        previous_status,
        machine.current.value,
        "success",
    ).inc()
    record = order_repository.update_status(order_id, machine.current.value)
    tracker.success()
    return _serialize_order(record)
