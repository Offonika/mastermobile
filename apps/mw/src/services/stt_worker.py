"""Background worker that processes STT jobs from Redis."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter, sleep
from typing import Protocol

from loguru import logger
from sqlalchemy.orm import Session

from apps.mw.src.config import get_settings
from apps.mw.src.db.session import SessionLocal
from apps.mw.src.observability import STT_JOB_DURATION_SECONDS, STT_JOBS_TOTAL
from apps.mw.src.services.stt_queue import DLQEntry, STTJob, STTQueue, create_redis_client

DEFAULT_MAX_RETRIES = 5
DEFAULT_BACKOFF_SECONDS = 2.0


@dataclass(slots=True)
class TranscriptionResult:
    """Successful transcription metadata."""

    transcript_path: str
    language: str | None = None


class SpeechToTextProvider(Protocol):
    """Simple protocol for transcription providers."""

    def transcribe(self, job: STTJob) -> TranscriptionResult:  # pragma: no cover - Protocol
        ...


class TranscriptionError(Exception):
    """Raised by providers when a transcription attempt failed."""

    def __init__(self, status_code: int | None, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class PlaceholderTranscriber:
    """A minimal local transcriber used until a real backend is wired in."""

    def __init__(self, transcripts_dir: Path) -> None:
        self._transcripts_dir = transcripts_dir

    def transcribe(self, job: STTJob) -> TranscriptionResult:
        self._transcripts_dir.mkdir(parents=True, exist_ok=True)
        target = self._transcripts_dir / f"{job.call_id}.txt"
        if not target.exists():
            target.write_text(
                "Transcription placeholder. Configure a real STT provider to replace this output.\n",
                encoding="utf-8",
            )
        return TranscriptionResult(transcript_path=str(target), language=job.language)


class STTWorker:
    """Long-running worker that processes STT jobs with retry semantics."""

    def __init__(
        self,
        queue: STTQueue,
        transcriber: SpeechToTextProvider,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
        idle_sleep_seconds: float = 1.0,
    ) -> None:
        self._queue = queue
        self._transcriber = transcriber
        self._session_factory = session_factory
        self._max_retries = max(1, max_retries)
        self._base_backoff = max(0.1, base_backoff_seconds)
        self._idle_sleep = max(0.1, idle_sleep_seconds)

    def run_forever(self, *, timeout: int = 5) -> None:
        """Blocking loop that keeps polling the queue for new jobs."""

        logger.info("Starting STT worker loop")
        while True:  # pragma: no cover - integration loop
            handled = self.process_next(timeout=timeout)
            if not handled:
                sleep(self._idle_sleep)

    def process_next(self, *, timeout: int | None = None) -> bool:
        """Process a single job from the queue."""

        job = self._queue.fetch_job(timeout=timeout)
        if job is None:
            return False

        logger.bind(call_id=job.call_id, engine=job.engine).info("Processing STT job")
        start = perf_counter()
        session = self._session_factory()
        try:
            record = self._queue.mark_transcribing(session, job)
            if record is None:
                STT_JOBS_TOTAL.labels(status="missing_record").inc()
                self._queue.mark_processed(job)
                return True

            result = self._transcribe_with_retry(session, job)
            if result is None:
                return True

            self._queue.record_success(
                session,
                job,
                transcript_path=result.transcript_path,
                transcript_lang=result.language,
            )
            STT_JOBS_TOTAL.labels(status="success").inc()
            logger.bind(call_id=job.call_id, engine=job.engine).info(
                "STT job completed",
            )
            return True
        finally:
            session.close()
            STT_JOB_DURATION_SECONDS.observe(perf_counter() - start)

    def _transcribe_with_retry(self, session: Session, job: STTJob) -> TranscriptionResult | None:
        """Execute the transcription with exponential backoff for retryable errors."""

        attempt = 0
        while True:
            try:
                return self._transcriber.transcribe(job)
            except TranscriptionError as exc:
                attempt += 1
                status_code = exc.status_code
                message = str(exc)
                if status_code is not None and 400 <= status_code < 500:
                    self._handle_client_failure(session, job, status_code, message)
                    return None

                if attempt >= self._max_retries:
                    self._handle_exhausted_retries(session, job, status_code, message)
                    return None

                delay = self._base_backoff * (2 ** (attempt - 1))
                STT_JOBS_TOTAL.labels(status="retry").inc()
                logger.bind(
                    call_id=job.call_id,
                    engine=job.engine,
                    attempt=attempt,
                    status_code=status_code,
                    delay=delay,
                ).warning("Retrying STT job after server error")
                sleep(delay)
            except Exception as exc:  # pragma: no cover - defensive guard
                attempt += 1
                if attempt >= self._max_retries:
                    reason = str(exc)
                    self._queue.record_failure(
                        session,
                        job,
                        error_code="unexpected_error",
                        error_message=reason,
                    )
                    self._queue.push_to_dlq(DLQEntry(job=job, reason=reason))
                    STT_JOBS_TOTAL.labels(status="dlq").inc()
                    logger.bind(call_id=job.call_id, engine=job.engine).exception(
                        "Unexpected STT worker failure",
                    )
                    return None

                delay = self._base_backoff * (2 ** (attempt - 1))
                STT_JOBS_TOTAL.labels(status="retry").inc()
                logger.bind(
                    call_id=job.call_id,
                    engine=job.engine,
                    attempt=attempt,
                    delay=delay,
                ).exception("Retrying after unexpected STT worker error")
                sleep(delay)

    def _handle_client_failure(
        self,
        session: Session,
        job: STTJob,
        status_code: int,
        message: str,
    ) -> None:
        """Record a non-retryable HTTP error and push to the DLQ."""

        reason = f"{status_code}: {message}"
        self._queue.record_failure(
            session,
            job,
            error_code=f"http_{status_code}",
            error_message=message,
        )
        self._queue.push_to_dlq(
            DLQEntry(job=job, reason=reason, status_code=status_code),
        )
        STT_JOBS_TOTAL.labels(status="dlq").inc()
        logger.bind(call_id=job.call_id, engine=job.engine, status_code=status_code).error(
            "STT job moved to DLQ after client error",
        )

    def _handle_exhausted_retries(
        self,
        session: Session,
        job: STTJob,
        status_code: int | None,
        message: str,
    ) -> None:
        """Persist a failure when retries are exhausted."""

        error_code = "max_retries"
        reason = message if status_code is None else f"{status_code}: {message}"
        self._queue.record_failure(
            session,
            job,
            error_code=error_code,
            error_message=reason,
        )
        self._queue.push_to_dlq(
            DLQEntry(job=job, reason=reason, status_code=status_code),
        )
        STT_JOBS_TOTAL.labels(status="dlq").inc()
        logger.bind(call_id=job.call_id, engine=job.engine, status_code=status_code).error(
            "STT job moved to DLQ after exhausting retries",
        )


def main() -> None:  # pragma: no cover - CLI entry point
    """Run the worker using the default Redis connection."""

    settings = get_settings()
    redis_client = create_redis_client(settings)
    queue = STTQueue(redis_client)
    transcripts_dir = Path(settings.local_storage_dir) / "transcripts"
    transcriber = PlaceholderTranscriber(transcripts_dir)

    worker = STTWorker(queue, transcriber)
    worker.run_forever()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
