"""Administrative endpoints for managing STT DLQ jobs."""
from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from redis import Redis
from sqlalchemy.orm import Session

from apps.mw.src.api.dependencies import (
    Principal,
    ProblemDetailException,
    build_error,
    require_admin,
)
from apps.mw.src.api.schemas import STTDLQRequeueResponse, STTJobPayload
from apps.mw.src.db.session import get_session
from apps.mw.src.services.stt_queue import STTQueue, create_redis_client
from loguru import logger

router = APIRouter(
    prefix="/api/v1/admin/stt",
    tags=["admin", "stt"],
)


def _get_stt_queue() -> Generator[STTQueue, None, None]:
    redis_client: Redis = create_redis_client()
    queue = STTQueue(redis_client)
    try:
        yield queue
    finally:
        redis_client.close()


@router.post(
    "/dlq/{entry_id}/requeue",
    response_model=STTDLQRequeueResponse,
    status_code=status.HTTP_200_OK,
    summary="Requeue a Speech-to-Text DLQ entry",
)
def requeue_stt_dlq_entry(
    entry_id: str,
    *,
    session: Session = Depends(get_session),
    queue: STTQueue = Depends(_get_stt_queue),
    admin: Principal = Depends(require_admin),
) -> STTDLQRequeueResponse:
    """Requeue a DLQ job by identifier returning the restored metadata."""

    request_id = admin.request_id
    entry = queue.requeue_dlq_entry(session, entry_id)
    if entry is None:
        raise ProblemDetailException(
            build_error(
                status.HTTP_404_NOT_FOUND,
                title="DLQ entry not found",
                detail="Requested DLQ entry could not be located.",
                request_id=request_id,
            )
        )

    audit_context = {
        "audit": True,
        "event": "stt_dlq_requeue",
        "entry_id": entry_id,
        "who": admin.subject,
        "when": datetime.now(tz=UTC).isoformat(),
        "why": "manual_requeue",
        "request_id": request_id,
        "call_id": entry.job.call_id,
        "record_id": entry.job.record_id,
    }
    logger.bind(**audit_context).info("Admin requeued STT DLQ entry", reason=entry.reason)

    job = entry.job
    return STTDLQRequeueResponse(
        status="requeued",
        entry_id=entry_id,
        job=STTJobPayload(
            record_id=job.record_id,
            call_id=job.call_id,
            recording_url=job.recording_url,
            engine=job.engine,
            language=job.language,
        ),
        reason=entry.reason,
        failed_at=entry.failed_at,
        status_code=entry.status_code,
    )
