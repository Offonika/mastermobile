"""Persistence helpers for audit logging."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from apps.mw.src.db.models import AuditLog
from apps.mw.src.services.stt_queue import STTJob
 
 
class AuditLogRepository:
    """Simple repository responsible for persisting audit entries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        actor: str,
        action: str,
        job_reference: str,
        job_payload: dict[str, Any],
        reason: str,
    ) -> AuditLog:
        entry = AuditLog(
            actor=actor,
            action=action,
            job_reference=job_reference,
            job_payload=job_payload,
            reason=reason,
        )
        self._session.add(entry)
        self._session.commit()
        self._session.refresh(entry)
        return entry


class AuditLogService:
    """High level service for writing audit trail events."""

    def __init__(self, session: Session) -> None:
        self._repository = AuditLogRepository(session)

    def log_dlq_replay(self, *, actor: str, job: STTJob, reason: str) -> AuditLog:
        """Persist a DLQ replay event describing the affected job."""

        payload = job.to_payload()
        return self._repository.create(
            actor=actor,
            action="stt_dlq_replay",
            job_reference=str(job.record_id),
            job_payload=payload,
            reason=reason,
        )
