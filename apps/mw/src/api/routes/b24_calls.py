"""Endpoints for exporting Bitrix24 call records in CSV and JSON formats."""
from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apps.mw.src.api.dependencies import ProblemDetailException, build_error, provide_request_id
from apps.mw.src.db.models import CallRecord
from apps.mw.src.db.session import get_session


class B24CallRecordPayload(BaseModel):
    """Representation of a Bitrix24 call record returned by the export API."""

    model_config = ConfigDict(from_attributes=True)

    call_id: str
    record_id: str | None = None
    employee_id: str | None = None
    call_started_at: datetime | None = None
    from_number: str | None = None
    to_number: str | None = None
    direction: str | None = None
    duration_sec: int
    recording_url: str | None = None
    transcript_path: str | None = None
    transcript_lang: str | None = None
    has_text: bool

    @classmethod
    def from_record(cls, record: CallRecord) -> "B24CallRecordPayload":
        """Build a payload object using database record attributes."""

        return cls(
            call_id=record.call_id,
            record_id=record.record_id,
            employee_id=getattr(record, "employee_id", None),
            call_started_at=getattr(record, "call_started_at", None),
            from_number=getattr(record, "from_number", None),
            to_number=getattr(record, "to_number", None),
            direction=getattr(record, "direction", None),
            duration_sec=record.duration_sec,
            recording_url=getattr(record, "recording_url", None),
            transcript_path=getattr(record, "transcript_path", None),
            transcript_lang=getattr(record, "transcript_lang", None),
            has_text=bool(getattr(record, "transcript_path", None)),
        )


router = APIRouter(
    prefix="/api/v1/b24-calls",
    tags=["b24-calls"],
    dependencies=[Depends(provide_request_id)],
)

_CSV_HEADERS = [
    "call_id",
    "record_id",
    "employee_id",
    "call_started_at",
    "from_number",
    "to_number",
    "direction",
    "duration_sec",
    "recording_url",
    "transcript_path",
    "transcript_lang",
    "has_text",
]


def _encode_row(values: list[str], *, include_bom: bool = False) -> bytes:
    """Serialize a list of values into a UTF-8 encoded CSV row."""

    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(values)
    payload = buffer.getvalue()
    if include_bom:
        payload = "\ufeff" + payload
    return payload.encode("utf-8")


def _csv_row(record: CallRecord) -> list[str]:
    """Convert a call record into CSV field values."""

    payload = B24CallRecordPayload.from_record(record)

    def _format_datetime(value: datetime | None) -> str:
        return value.isoformat() if value else ""

    return [
        payload.call_id,
        payload.record_id or "",
        payload.employee_id or "",
        _format_datetime(payload.call_started_at),
        payload.from_number or "",
        payload.to_number or "",
        payload.direction or "",
        str(payload.duration_sec),
        payload.recording_url or "",
        payload.transcript_path or "",
        payload.transcript_lang or "",
        "true" if payload.has_text else "false",
    ]


def _stream_csv(records: Iterable[CallRecord]) -> Iterable[bytes]:
    """Yield UTF-8 encoded CSV chunks for streaming responses."""

    yield _encode_row(_CSV_HEADERS, include_bom=True)
    for record in records:
        yield _encode_row(_csv_row(record))


def _validate_period(
    response: Response,
    *,
    date_from: datetime | None,
    date_to: datetime | None,
) -> None:
    """Ensure requested date range boundaries form a valid interval."""

    if date_from and date_to and date_to < date_from:
        request_id = response.headers.get("X-Request-Id")
        error = build_error(
            status.HTTP_400_BAD_REQUEST,
            title="Invalid date range",
            detail="date_to must be greater than or equal to date_from.",
            request_id=request_id,
        )
        raise ProblemDetailException(error)


def _build_statement(
    *,
    employee_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    has_text: bool | None,
):
    """Construct a filtered select statement for call records."""

    stmt = select(CallRecord)

    if employee_id:
        stmt = stmt.where(CallRecord.employee_id == employee_id.strip())
    if date_from:
        stmt = stmt.where(CallRecord.call_started_at >= date_from)
    if date_to:
        stmt = stmt.where(CallRecord.call_started_at <= date_to)
    if has_text is not None:
        if has_text:
            stmt = stmt.where(
                CallRecord.transcript_path.isnot(None),
                CallRecord.transcript_path != "",
            )
        else:
            stmt = stmt.where(
                or_(
                    CallRecord.transcript_path.is_(None),
                    CallRecord.transcript_path == "",
                )
            )

    return stmt.order_by(CallRecord.call_started_at.asc(), CallRecord.id.asc())


def _build_filename(*, date_from: datetime | None, date_to: datetime | None) -> str:
    """Generate a deterministic CSV filename based on requested range."""

    if date_from or date_to:
        start = date_from.strftime("%Y%m%dT%H%M%S") if date_from else "start"
        end = date_to.strftime("%Y%m%dT%H%M%S") if date_to else "end"
        return f"b24_calls_{start}_{end}.csv"
    return "b24_calls_export.csv"


@router.get(
    "/export.csv",
    summary="Download Bitrix24 call records as CSV",
    response_class=StreamingResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid date range.",
        }
    },
)
def export_b24_calls_csv(
    response: Response,
    employee_id: str | None = Query(
        default=None,
        description="Filter by Bitrix24 employee identifier.",
        max_length=128,
    ),
    date_from: datetime | None = Query(
        default=None,
        description="Start of the call start timestamp range (inclusive).",
    ),
    date_to: datetime | None = Query(
        default=None,
        description="End of the call start timestamp range (inclusive).",
    ),
    has_text: bool | None = Query(
        default=None,
        description="When true, return only calls that have a transcript; false for missing transcripts.",
    ),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Stream filtered Bitrix24 call records as CSV."""

    _validate_period(response, date_from=date_from, date_to=date_to)

    stmt = _build_statement(
        employee_id=employee_id.strip() if employee_id else None,
        date_from=date_from,
        date_to=date_to,
        has_text=has_text,
    )
    records = session.execute(stmt).scalars().all()

    stream = _stream_csv(records)
    streaming_response = StreamingResponse(stream, media_type="text/csv; charset=utf-8")
    streaming_response.headers["Content-Disposition"] = (
        f'attachment; filename="{_build_filename(date_from=date_from, date_to=date_to)}"'
    )
    streaming_response.headers.setdefault("Cache-Control", "no-store")

    request_id = response.headers.get("X-Request-Id")
    if request_id:
        streaming_response.headers["X-Request-Id"] = request_id

    return streaming_response


@router.get(
    "/export.json",
    summary="List Bitrix24 call records as JSON",
    response_model=list[B24CallRecordPayload],
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid date range.",
        }
    },
)
def export_b24_calls_json(
    response: Response,
    employee_id: str | None = Query(
        default=None,
        description="Filter by Bitrix24 employee identifier.",
        max_length=128,
    ),
    date_from: datetime | None = Query(
        default=None,
        description="Start of the call start timestamp range (inclusive).",
    ),
    date_to: datetime | None = Query(
        default=None,
        description="End of the call start timestamp range (inclusive).",
    ),
    has_text: bool | None = Query(
        default=None,
        description="When true, return only calls that have a transcript; false for missing transcripts.",
    ),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Return filtered Bitrix24 call records as a JSON array."""

    _validate_period(response, date_from=date_from, date_to=date_to)

    stmt = _build_statement(
        employee_id=employee_id.strip() if employee_id else None,
        date_from=date_from,
        date_to=date_to,
        has_text=has_text,
    )
    records = session.execute(stmt).scalars().all()
    payload = [B24CallRecordPayload.from_record(record).model_dump(mode="json") for record in records]

    json_response = JSONResponse(content=payload)
    json_response.headers.setdefault("Cache-Control", "no-store")

    request_id = response.headers.get("X-Request-Id")
    if request_id:
        json_response.headers["X-Request-Id"] = request_id

    return json_response
