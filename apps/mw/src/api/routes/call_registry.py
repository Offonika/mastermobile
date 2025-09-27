"""Endpoints for exporting Bitrix24 call registry CSV reports."""
from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from io import StringIO
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.mw.src.api.dependencies import ProblemDetailException, build_error, provide_request_id
from apps.mw.src.db.models import CallRecord
from apps.mw.src.db.session import get_session

_FIELD_ORDER = [
    "run_id",
    "call_id",
    "record_id",
    "datetime_start",
    "direction",
    "employee",
    "from",
    "to",
    "duration_sec",
    "recording_url",
    "transcript_path",
    "text_preview",
    "transcription_cost",
    "currency_code",
    "language",
    "status",
    "error_code",
    "retry_count",
    "checksum",
    "summary_path",
]

_CSV_HEADERS = _FIELD_ORDER

router = APIRouter(
    prefix="/api/v1/call-registry",
    tags=["call-registry"],
    dependencies=[Depends(provide_request_id)],
)


def _format_datetime(value: datetime | None) -> str:
    """Render datetimes in ISO-8601 format (empty string when missing)."""

    if value is None:
        return ""
    return value.isoformat()


def _format_decimal(value: Decimal | None) -> str:
    """Render decimals with two fractional digits for exports."""

    if value is None:
        return ""
    quantized = value.quantize(Decimal("0.01"))
    return format(quantized, "f")


def _enum_value(value: Any) -> str | None:
    """Return the string value for enums while handling ``None``."""

    if value is None:
        return None
    return getattr(value, "value", str(value))


def _record_payload(record: CallRecord) -> dict[str, Any]:
    """Convert a ``CallRecord`` into a serializable payload."""

    return {
        "run_id": str(record.run_id),
        "call_id": record.call_id,
        "record_id": record.record_id,
        "datetime_start": _format_datetime(record.started_at),
        "direction": _enum_value(record.direction),
        "employee": record.employee_id,
        "from": record.from_number,
        "to": record.to_number,
        "duration_sec": record.duration_sec,
        "recording_url": record.recording_url,
        "transcript_path": record.transcript_path,
        "text_preview": record.text_preview,
        "transcription_cost": _format_decimal(record.transcription_cost),
        "currency_code": record.currency_code,
        "language": record.language,
        "status": _enum_value(record.status),
        "error_code": record.error_code,
        "retry_count": record.retry_count,
        "checksum": record.checksum,
        "summary_path": record.summary_path,
    }


def _csv_value(value: Any) -> str:
    """Convert payload values into their CSV string representation."""

    if value is None:
        return ""
    return str(value)


def _encode_row(values: list[str], *, include_bom: bool = False) -> bytes:
    """Serialize a CSV row with semicolon delimiter and optional BOM."""

    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(values)
    payload = buffer.getvalue()
    if include_bom:
        payload = "\ufeff" + payload
    return payload.encode("utf-8")


def _row_values(record: CallRecord) -> list[str]:
    """Extract CSV field values from a call record."""

    payload = _record_payload(record)
    return [_csv_value(payload[field]) for field in _FIELD_ORDER]


def _stream_csv(rows: Iterable[CallRecord]) -> Iterable[bytes]:
    """Yield the call registry CSV as UTF-8 encoded chunks."""

    yield _encode_row(_CSV_HEADERS, include_bom=True)
    for record in rows:
        yield _encode_row(_row_values(record))


def _build_statement(period_from: datetime, period_to: datetime):
    return (
        select(CallRecord)
        .where(CallRecord.started_at.isnot(None))
        .where(CallRecord.started_at >= period_from)
        .where(CallRecord.started_at <= period_to)
        .order_by(CallRecord.started_at.asc(), CallRecord.id.asc())
    )


def _validate_period(
    response: Response, period_from: datetime, period_to: datetime
) -> tuple[datetime, datetime]:
    if period_to < period_from:
        error = build_error(
            status.HTTP_400_BAD_REQUEST,
            title="Invalid period range",
            detail="period_to must be greater than or equal to period_from.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error)
    return period_from, period_to


@router.get(
    "",
    summary="Download call registry CSV",
    response_class=StreamingResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid period range.",
        }
    },
)
def export_call_registry(
    response: Response,
    period_from: datetime = Query(..., description="Start of the call start timestamp range."),
    period_to: datetime = Query(..., description="End of the call start timestamp range."),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Stream a semicolon-separated CSV of call records for the requested period."""

    period_from, period_to = _validate_period(response, period_from, period_to)

    stmt = _build_statement(period_from, period_to)
    records = session.scalars(stmt).all()

    filename = (
        f"registry/calls_{period_from.strftime('%Y%m%dT%H%M%S')}"
        f"_{period_to.strftime('%Y%m%dT%H%M%S')}.csv"
    )

    stream = _stream_csv(records)
    streaming_response = StreamingResponse(stream, media_type="text/csv; charset=utf-8")
    streaming_response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    streaming_response.headers.setdefault("Cache-Control", "no-store")

    request_id = response.headers.get("X-Request-Id")
    if request_id:
        streaming_response.headers["X-Request-Id"] = request_id

    return streaming_response


@router.get(
    "/json",
    summary="Download call registry JSON",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid period range.",
        }
    },
)
def export_call_registry_json(
    response: Response,
    period_from: datetime = Query(..., description="Start of the call start timestamp range."),
    period_to: datetime = Query(..., description="End of the call start timestamp range."),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Return the call registry rows as a JSON array preserving CSV order."""

    period_from, period_to = _validate_period(response, period_from, period_to)

    stmt = _build_statement(period_from, period_to)
    records = session.scalars(stmt).all()
    return [_record_payload(record) for record in records]
