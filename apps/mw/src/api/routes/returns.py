"""Routes exposing CRUD operations for return documents."""

from __future__ import annotations

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from ...api.dependencies import inject_request_id, require_idempotency_key, validate_idempotency
from ...api.schemas.returns import (
    Error,
    PaginatedReturns,
    Return as ReturnSchema,
    ReturnCreate,
    ReturnLine as ReturnLineSchema,
    ReturnLinePayload,
)
from ...db.models import Return as ReturnModel
from ...db.models import ReturnLine as ReturnLineModel
from ...db.session import get_session

router = APIRouter(prefix="/api/v1/returns", tags=["returns"])


def _to_schema(return_obj: ReturnModel) -> ReturnSchema:
    """Convert a SQLAlchemy return instance into a Pydantic schema."""

    items = [
        ReturnLineSchema(
            line_id=line.line_id,
            sku=line.sku,
            qty=line.qty,
            quality=line.quality,
            reason_id=line.reason_id,
            reason_note=line.reason_note,
            photos=line.photos,
            imei=line.imei,
            serial=line.serial,
        )
        for line in sorted(return_obj.lines, key=lambda obj: obj.line_id)
    ]

    return ReturnSchema(
        id=return_obj.return_id,
        status=return_obj.status,
        source=return_obj.source,
        courier_id=return_obj.courier_id,
        order_id_1c=return_obj.order_id_1c,
        manager_id=return_obj.manager_id,
        comment=return_obj.comment,
        created_at=return_obj.created_at,
        updated_at=return_obj.updated_at,
        items=items,
    )


def _not_found(request_id: str, return_id: UUID) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=Error(
            type="about:blank",
            title="Return not found",
            status=status.HTTP_404_NOT_FOUND,
            detail=f"Return {return_id} does not exist.",
            request_id=request_id,
        ).model_dump(exclude_none=True),
    )


def _bad_request(request_id: str, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=Error(
            type="about:blank",
            title="Invalid request",
            status=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            request_id=request_id,
        ).model_dump(exclude_none=True),
    )


def _build_line_models(
    session: Session,
    items: list[ReturnLinePayload],
) -> list[ReturnLineModel]:
    """Allocate primary keys for new return line rows."""

    last_id = session.scalar(select(func.max(ReturnLineModel.id))) or 0
    models: list[ReturnLineModel] = []
    for index, item in enumerate(items, start=1):
        models.append(
            ReturnLineModel(
                id=last_id + index,
                line_id=item.line_id,
                sku=item.sku,
                qty=item.qty,
                quality=item.quality,
                reason_id=item.reason_id,
                reason_note=item.reason_note,
                photos=item.photos,
                imei=item.imei,
                serial=item.serial,
            )
        )
    return models


@router.get("", response_model=PaginatedReturns)
def list_returns(
    *,
    request_id: str = Depends(inject_request_id),
    session: Session = Depends(get_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedReturns:
    """Return a paginated list of return documents."""

    total_items = session.scalar(select(func.count()).select_from(ReturnModel)) or 0

    query = (
        select(ReturnModel)
        .options(selectinload(ReturnModel.lines))
        .order_by(ReturnModel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = [
        _to_schema(result)
        for result in session.execute(query).scalars().unique().all()
    ]

    total_pages = math.ceil(total_items / page_size) if total_items else 0
    has_next = page * page_size < total_items

    return PaginatedReturns(
        items=items,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=has_next,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ReturnSchema,
)
def create_return(
    *,
    request: Request,
    response: Response,
    payload: ReturnCreate,
    request_id: str = Depends(inject_request_id),
    session: Session = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> ReturnSchema:
    """Create a new return document."""

    validate_idempotency(
        key=idempotency_key,
        payload=payload,
        scope=f"{request.method}:{request.url.path}",
        request_id=request_id,
    )

    return_obj = ReturnModel(
        source=payload.source,
        courier_id=payload.courier_id,
        order_id_1c=payload.order_id_1c,
        manager_id=payload.manager_id,
        comment=payload.comment,
    )

    if payload.status is not None:
        return_obj.status = payload.status

    for line_model in _build_line_models(session, payload.items):
        return_obj.lines.append(line_model)

    session.add(return_obj)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise _bad_request(request_id, "Failed to persist return due to integrity violation.") from exc

    session.refresh(return_obj)

    response.headers["Location"] = f"/api/v1/returns/{return_obj.return_id}"
    return _to_schema(return_obj)


@router.get("/{return_id}", response_model=ReturnSchema)
def get_return(
    *,
    return_id: UUID,
    request_id: str = Depends(inject_request_id),
    session: Session = Depends(get_session),
) -> ReturnSchema:
    """Retrieve a single return document."""

    query = (
        select(ReturnModel)
        .options(selectinload(ReturnModel.lines))
        .where(ReturnModel.return_id == return_id)
    )
    result = session.execute(query).scalars().first()

    if result is None:
        raise _not_found(request_id, return_id)

    return _to_schema(result)


@router.put("/{return_id}", response_model=ReturnSchema)
def update_return(
    *,
    request: Request,
    return_id: UUID,
    payload: ReturnCreate,
    request_id: str = Depends(inject_request_id),
    session: Session = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> ReturnSchema:
    """Update an existing return document."""

    validate_idempotency(
        key=idempotency_key,
        payload=payload,
        scope=f"{request.method}:{request.url.path}",
        request_id=request_id,
    )

    query = (
        select(ReturnModel)
        .options(selectinload(ReturnModel.lines))
        .where(ReturnModel.return_id == return_id)
    )
    result = session.execute(query).scalars().first()

    if result is None:
        raise _not_found(request_id, return_id)

    result.source = payload.source
    result.courier_id = payload.courier_id
    result.order_id_1c = payload.order_id_1c
    result.manager_id = payload.manager_id
    result.comment = payload.comment

    if payload.status is not None:
        result.status = payload.status

    result.lines.clear()
    for line_model in _build_line_models(session, payload.items):
        result.lines.append(line_model)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise _bad_request(request_id, "Failed to persist return due to integrity violation.") from exc

    session.refresh(result)
    return _to_schema(result)


@router.delete("/{return_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_return(
    *,
    request: Request,
    return_id: UUID,
    request_id: str = Depends(inject_request_id),
    session: Session = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> None:
    """Delete an existing return document."""

    validate_idempotency(
        key=idempotency_key,
        payload=None,
        scope=f"{request.method}:{request.url.path}",
        request_id=request_id,
    )

    result = session.get(ReturnModel, return_id)

    if result is None:
        raise _not_found(request_id, return_id)

    session.delete(result)

    try:
        session.commit()
    except SQLAlchemyError as exc:  # pragma: no cover - defensive
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Error(
                type="about:blank",
                title="Deletion failed",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected error during deletion.",
                request_id=request_id,
            ).model_dump(exclude_none=True),
        ) from exc
