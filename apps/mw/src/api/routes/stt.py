"""Speech-to-Text queue administration endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from apps.mw.src.api.dependencies import (
    ProblemDetailException,
    build_error,
    provide_request_id,
    require_admin_actor,
)
from apps.mw.src.api.schemas import DLQReplayRequest, DLQReplayResponse
from apps.mw.src.db.session import get_session
from apps.mw.src.services.audit import AuditLogService
from apps.mw.src.services.stt_queue import STTQueue, create_redis_client

router = APIRouter(
    prefix="/api/v1/stt",
    tags=["stt"],
    dependencies=[Depends(provide_request_id)],
)


def get_stt_queue() -> STTQueue:
    """FastAPI dependency returning a queue instance."""

    client = create_redis_client()
    return STTQueue(client)


@router.post(
    "/dlq/replay",
    response_model=DLQReplayResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Replay an STT job from the DLQ",
)
async def replay_dlq_job(
    payload: DLQReplayRequest,
    actor: str = Depends(require_admin_actor),
    queue: STTQueue = Depends(get_stt_queue),
    session: Session = Depends(get_session),
) -> DLQReplayResponse:
    """Requeue a specific STT job from the DLQ and log the action."""

    job = queue.replay_dlq_job(payload.record_id)
    if job is None:
        raise ProblemDetailException(
            build_error(
                status.HTTP_404_NOT_FOUND,
                title="DLQ job not found",
                detail="Requested job is not present in the DLQ.",
            )
        )

    AuditLogService(session).log_dlq_replay(actor=actor, job=job, reason=payload.reason)
    return DLQReplayResponse(status="requeued", job=job.to_payload())
