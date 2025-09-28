"""Endpoints for exporting Bitrix24 call registry CSV reports."""
from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from io import StringIO
from time import perf_counter

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.mw.src.api.dependencies import ProblemDetailException, build_error, provide_request_id
from apps.mw.src.db.models import CallRecord
from apps.mw.src.db.session import get_session
from apps.mw.src.observability import CALL_EXPORT_DURATION_SECONDS, CALL_EXPORT_REPORTS_TOTAL

_CSV_HEADERS = [
    "run_id",
    "call_id",
    "record_id",
    "employee",
    "datetime_start",
    "direction",
    "from",
    "to",
    "duration_sec",
    "recording_url",
    "transcript_path",
    "summary_path",
    "text_preview",
    "transcription_cost",
    "currency_code",
    "language",
    "status",
    "error_code",
    "retry_count",
    "checksum",
]

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

    status = record.status.value if hasattr(record.status, "value") else str(record.status)

    def _format_decimal(value: Decimal | None) -> str:
        return f"{value:.2f}" if value is not None else ""

    return [
        str(getattr(record, "run_id", "")),
        record.call_id,
        getattr(record, "record_id", "") or "",
        getattr(record, "employee_id", None) or "",
        _format_datetime(getattr(record, "call_started_at", None)),
        getattr(record, "direction", None) or "",
        getattr(record, "from_number", None) or "",
        getattr(record, "to_number", None) or "",
        str(record.duration_sec),
        getattr(record, "recording_url", None) or "",
        getattr(record, "transcript_path", None) or "",
        getattr(record, "summary_path", None) or "",
        getattr(record, "text_preview", None) or "",
        _format_decimal(getattr(record, "transcription_cost", None)),
        getattr(record, "currency_code", None) or "",
        getattr(record, "language", None) or "",
        status,
        getattr(record, "error_code", None) or "",
        str(getattr(record, "attempts", 0)),
        getattr(record, "checksum", None) or "",
    ]


def _stream_csv(rows: Iterable[CallRecord]) -> Iterable[bytes]:
    """Yield the call registry CSV as UTF-8 encoded chunks."""

    yield _encode_row(_CSV_HEADERS, include_bom=True)
    for record in rows:
        yield _encode_row(_row_values(record))


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

    if period_to < period_from:
        CALL_EXPORT_DURATION_SECONDS.labels(stage="report", status="error").observe(0.0)
        error = build_error(
            status.HTTP_400_BAD_REQUEST,
            title="Invalid period range",
            detail="period_to must be greater than or equal to period_from.",
            request_id=response.headers.get("X-Request-Id"),
        )
        raise ProblemDetailException(error)

    started_at = perf_counter()

    stmt = (
        select(CallRecord)
        .where(CallRecord.call_started_at.isnot(None))
        .where(CallRecord.call_started_at >= period_from)
        .where(CallRecord.call_started_at <= period_to)
        .order_by(CallRecord.call_started_at.asc(), CallRecord.id.asc())
    )
    rows = session.execute(stmt).scalars().all()

    filename = (
        f"registry/calls_{period_from.strftime('%Y%m%dT%H%M%S')}"
        f"_{period_to.strftime('%Y%m%dT%H%M%S')}.csv"
    )

    stream = _stream_csv(rows)
    streaming_response = StreamingResponse(stream, media_type="text/csv; charset=utf-8")
    streaming_response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    streaming_response.headers.setdefault("Cache-Control", "no-store")

    request_id = response.headers.get("X-Request-Id")
    if request_id:
        streaming_response.headers["X-Request-Id"] = request_id

    CALL_EXPORT_DURATION_SECONDS.labels(stage="report", status="success").observe(
        perf_counter() - started_at
    )
    CALL_EXPORT_REPORTS_TOTAL.labels(format="csv").inc()

    return streaming_response
