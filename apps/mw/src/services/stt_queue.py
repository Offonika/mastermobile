"""Redis-backed queue helpers for Speech-to-Text jobs."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, cast

from loguru import logger
from redis import Redis
from sqlalchemy.orm import Session

from apps.mw.src.config import Settings, get_settings
from apps.mw.src.db.models import CallRecord, CallRecordStatus

STT_QUEUE_KEY: Final[str] = "stt:jobs"
STT_DLQ_KEY: Final[str] = "stt:jobs:dlq"
STT_PROCESSED_KEY: Final[str] = "stt:jobs:processed"


@dataclass(slots=True)
class STTJob:
    """Envelope for a single transcription job."""

    record_id: int
    call_id: str
    recording_url: str
    engine: str
    language: str | None = None

    @property
    def dedup_key(self) -> str:
        """Return a stable idempotency key for the job."""

        return f"{self.call_id}|{self.recording_url}|{self.engine}"

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serialisable payload."""

        return {
            "record_id": self.record_id,
            "call_id": self.call_id,
            "recording_url": self.recording_url,
            "engine": self.engine,
            "language": self.language,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> STTJob:
        """Create a job from a mapping payload."""

        try:
            record_id = int(payload["record_id"])
            call_id = str(payload["call_id"])
            recording_url = str(payload["recording_url"])
            engine = str(payload["engine"])
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError("payload is missing required fields") from exc

        language = payload.get("language")
        if language is not None:
            language = str(language)

        return cls(
            record_id=record_id,
            call_id=call_id,
            recording_url=recording_url,
            engine=engine,
            language=language,
        )

    @classmethod
    def from_json(cls, payload: str) -> STTJob:
        """Create a job from a JSON string."""

        data = json.loads(payload)
        if not isinstance(data, Mapping):  # pragma: no cover - defensive
            raise ValueError("payload must be a JSON object")
        return cls.from_mapping(data)


@dataclass(slots=True)
class DLQEntry:
    """Structured representation of a failed job."""

    job: STTJob
    reason: str
    status_code: int | None = None
    failed_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON payload describing the failure."""

        payload: dict[str, Any] = {
            "job": self.job.to_payload(),
            "reason": self.reason,
            "failed_at": self.failed_at.isoformat(),
        }
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        return payload


def create_redis_client(settings: Settings | None = None) -> Redis:
    """Create a Redis client configured from application settings."""

    settings = settings or get_settings()
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
    )


class STTQueue:
    """Redis-backed queue with idempotency and DLQ helpers."""

    def __init__(
        self,
        redis_client: Redis,
        *,
        queue_key: str = STT_QUEUE_KEY,
        dlq_key: str = STT_DLQ_KEY,
        processed_key: str = STT_PROCESSED_KEY,
    ) -> None:
        self._redis = redis_client
        self._queue_key = queue_key
        self._dlq_key = dlq_key
        self._processed_key = processed_key

    def enqueue(self, job: STTJob) -> None:
        """Append a job to the main queue respecting idempotency."""

        if self.is_processed(job):
            logger.bind(call_id=job.call_id, engine=job.engine).info(
                "Skipping enqueue for already processed STT job",
            )
            return

        self._redis.rpush(self._queue_key, json.dumps(job.to_payload()))

    def fetch_job(self, *, timeout: int | None = None) -> STTJob | None:
        """Pop the next job from the queue, skipping duplicates."""

        block = timeout is not None and timeout > 0
        wait_timeout = timeout or 0

        while True:
            item: str | None
            if block:
                result = self._redis.blpop([self._queue_key], timeout=wait_timeout)
                block = False
                wait_timeout = 0
                if result is None:
                    return None
                item = cast(str, result[1])
            else:
                item = self._redis.lpop(self._queue_key)
                if item is None:
                    return None

            job = STTJob.from_json(item)
            if self.is_processed(job):
                logger.bind(call_id=job.call_id, engine=job.engine).warning(
                    "Skipping duplicate STT job",
                )
                continue
            return job

    def is_processed(self, job: STTJob) -> bool:
        """Return whether the job's idempotency key has been processed."""

        return bool(self._redis.sismember(self._processed_key, job.dedup_key))

    def mark_processed(self, job: STTJob) -> None:
        """Persist the job idempotency key."""

        self._redis.sadd(self._processed_key, job.dedup_key)

    def push_to_dlq(self, entry: DLQEntry) -> None:
        """Append a failure entry to the dedicated DLQ."""

        self._redis.rpush(self._dlq_key, json.dumps(entry.to_payload()))

    def mark_transcribing(self, session: Session, job: STTJob) -> CallRecord | None:
        """Set the CallRecord to transcribing and bump attempt counters."""

        record = session.get(CallRecord, job.record_id)
        if record is None:
            logger.bind(call_id=job.call_id, record_id=job.record_id).warning(
                "CallRecord for STT job not found",
            )
            return None

        record.status = CallRecordStatus.TRANSCRIBING
        record.retry_count += 1
        record.last_retry_at = datetime.now(tz=UTC)
        session.commit()
        return record

    def record_success(
        self,
        session: Session,
        job: STTJob,
        *,
        transcript_path: str,
        language: str | None,
    ) -> None:
        """Persist successful transcription details on the CallRecord."""

        record = session.get(CallRecord, job.record_id)
        if record is None:
            logger.bind(call_id=job.call_id, record_id=job.record_id).error(
                "CallRecord missing when storing transcript",
            )
            return

        record.transcript_path = transcript_path
        record.language = language
        record.status = CallRecordStatus.COMPLETED
        record.error_code = None
        record.error_message = None
        record.last_retry_at = datetime.now(tz=UTC)
        session.commit()
        self.mark_processed(job)

    def record_failure(
        self,
        session: Session,
        job: STTJob,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        """Persist failure metadata on the CallRecord."""

        record = session.get(CallRecord, job.record_id)
        if record is None:
            logger.bind(call_id=job.call_id, record_id=job.record_id).error(
                "CallRecord missing when recording STT error",
            )
            return

        record.status = CallRecordStatus.ERROR
        record.error_code = error_code
        record.error_message = error_message
        record.last_retry_at = datetime.now(tz=UTC)
        session.commit()
        self.mark_processed(job)


__all__ = [
    "DLQEntry",
    "STTJob",
    "STTQueue",
    "create_redis_client",
    "STT_QUEUE_KEY",
    "STT_DLQ_KEY",
    "STT_PROCESSED_KEY",
]
