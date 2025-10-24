"""CRUD endpoints for managing returns."""
from __future__ import annotations

import math
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from apps.mw.src.api.dependencies import (
    IdempotencyContext,
    ProblemDetailException,
    build_error,
    enforce_idempotency_key,
    provide_request_id,
)
from apps.mw.src.api.schemas import Error, PaginatedReturns, Return, ReturnCreate, ReturnItem
from apps.mw.src.db.models import Return as ReturnModel
from apps.mw.src.db.models import ReturnLine as ReturnLineModel
from apps.mw.src.db.session import get_session

SessionDependency = Annotated[Session, Depends(get_session)]
ReturnIdPath = Annotated[UUID, Path(..., description="Identifier of the return.")]
PageQuery = Annotated[int, Query(ge=1, description="Page number to return.")]
PageSizeQuery = Annotated[
    int, Query(ge=1, le=100, description="Number of items per page.")
]
IdempotencyDependency = Annotated[IdempotencyContext, Depends(enforce_idempotency_key)]
IdempotencyKeyDependency = Annotated[str, Depends(enforce_idempotency_key)]

router = APIRouter(
    prefix="/api/v1/returns",
    tags=["returns"],
    dependencies=[Depends(provide_request_id)],
)


def _serialize_return(model: ReturnModel) -> Return:
    """Convert a SQLAlchemy return entity into a Pydantic schema."""

    items = [
        ReturnItem(
            line_id=line.line_id,
            sku=line.sku,
            qty=line.qty,
            quality=line.quality,
            reason_code=line.reason_code,
            reason_note=line.reason_note,
            photos=list(line.photos) if line.photos is not None else None,
            imei=line.imei,
            serial=line.serial,
        )
        for line in sorted(model.lines, key=lambda item: item.line_id)
    ]

    return Return(
        id=str(model.return_id),
        status=model.status,
        source=model.source,
        courier_id=model.courier_id,
        order_id_1c=model.order_id_1c,
        manager_id=model.manager_id,
        comment=model.comment,
        created_at=model.created_at,
        updated_at=model.updated_at,
        items=items,
    )


@router.get(
    "",
    response_model=PaginatedReturns,
    summary="List returns",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": Error, "description": "Invalid request parameters."},
    },
)
def list_returns(
    page: PageQuery = 1,
    page_size: PageSizeQuery = 20,
    *,
    session: SessionDependency,
) -> PaginatedReturns:
    """Return a paginated list of stored returns."""

    total_items = session.scalar(select(func.count(ReturnModel.return_id))) or 0
    offset = (page - 1) * page_size

    stmt = (
        select(ReturnModel)
        .options(selectinload(ReturnModel.lines))
        .order_by(ReturnModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    returns = session.scalars(stmt).all()

    total_pages = math.ceil(total_items / page_size) if total_items else 0
    has_next = page < total_pages

    return PaginatedReturns(
        items=[_serialize_return(record) for record in returns],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=has_next,
    )


def _allocate_line_ids(session: Session, count: int) -> list[int | None]:
    """Allocate primary keys for return lines when required by SQLite."""

    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "sqlite":
        max_id = session.scalar(select(func.max(ReturnLineModel.id))) or 0
        return [max_id + index + 1 for index in range(count)]
    return [None] * count


@router.post(
    "",
    response_model=Return,
    status_code=status.HTTP_201_CREATED,
    summary="Create a return",
    responses={
        status.HTTP_409_CONFLICT: {"model": Error, "description": "Idempotency conflict."},
    },
)
async def create_return(
    payload: ReturnCreate,
    response: Response,
    session: SessionDependency,
    idempotency: IdempotencyDependency,
) -> Return:
    """Persist a new return document together with its line items."""

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

    return_model = ReturnModel(
        return_id=uuid4(),
        source=payload.source,
        courier_id=payload.courier_id,
        order_id_1c=payload.order_id_1c,
        comment=payload.comment,
    )

    line_ids = _allocate_line_ids(session, len(payload.items))
    for line_pk, item in zip(line_ids, payload.items, strict=False):
        return_model.lines.append(
            ReturnLineModel(
                id=line_pk,
                line_id=str(uuid4()),
                sku=item.sku,
                qty=item.qty,
                quality=item.quality,
                reason_code=item.reason_code,
                reason_note=item.reason_note,
                photos=list(item.photos) if item.photos is not None else None,
                imei=item.imei,
                serial=item.serial,
            )
        )

    session.add(return_model)
    session.commit()
    session.refresh(return_model)

    response.headers["Location"] = f"/api/v1/returns/{return_model.return_id}"
    serialized = _serialize_return(return_model)
    idempotency.store_response(
        status_code=status.HTTP_201_CREATED,
        payload=serialized,
        headers={"Location": response.headers["Location"]},
    )
    return serialized


@router.get(
    "/{return_id}",
    response_model=Return,
    summary="Retrieve a return",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": Error, "description": "Return was not found."},
    },
)
def get_return(
    response: Response,
    return_id: ReturnIdPath,
    session: SessionDependency,
) -> Return:
    """Fetch a single return by its identifier."""

    record = session.get(ReturnModel, return_id)
    if record is None:
        error = build_error(
            status.HTTP_404_NOT_FOUND,
            title="Return not found",
            detail=f"Return {return_id} was not found.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error)

    session.refresh(record)
    return _serialize_return(record)


@router.put(
    "/{return_id}",
    response_model=Return,
    summary="Update a return",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": Error, "description": "Return was not found."},
        status.HTTP_409_CONFLICT: {"model": Error, "description": "Idempotency conflict."},
    },
)
async def update_return(
    response: Response,
    payload: ReturnCreate,
    return_id: ReturnIdPath,
    session: SessionDependency,
    _idempotency_key: IdempotencyKeyDependency,
) -> Return:
    """Replace return fields and line items with supplied payload."""

    record = session.get(ReturnModel, return_id)
    if record is None:
        error = build_error(
            status.HTTP_404_NOT_FOUND,
            title="Return not found",
            detail=f"Return {return_id} was not found.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error)

    record.source = payload.source
    record.courier_id = payload.courier_id
    record.order_id_1c = payload.order_id_1c
    record.comment = payload.comment

    record.lines.clear()
    session.flush()

    line_ids = _allocate_line_ids(session, len(payload.items))
    for line_pk, item in zip(line_ids, payload.items, strict=False):
        record.lines.append(
            ReturnLineModel(
                id=line_pk,
                line_id=str(uuid4()),
                sku=item.sku,
                qty=item.qty,
                quality=item.quality,
                reason_code=item.reason_code,
                reason_note=item.reason_note,
                photos=list(item.photos) if item.photos is not None else None,
                imei=item.imei,
                serial=item.serial,
            )
        )

    session.add(record)
    session.commit()
    session.refresh(record)

    return _serialize_return(record)


@router.delete(
    "/{return_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a return",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": Error, "description": "Return was not found."},
        status.HTTP_409_CONFLICT: {"model": Error, "description": "Idempotency conflict."},
    },
)
async def delete_return(
    response: Response,
    return_id: ReturnIdPath,
    session: SessionDependency,
    _idempotency_key: IdempotencyKeyDependency,
) -> None:
    """Remove a return and all associated line items."""

    record = session.get(ReturnModel, return_id)
    if record is None:
        error = build_error(
            status.HTTP_404_NOT_FOUND,
            title="Return not found",
            detail=f"Return {return_id} was not found.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error)

    session.delete(record)
    session.commit()

    response.status_code = status.HTTP_204_NO_CONTENT
