from __future__ import annotations

import socket
from pathlib import Path
from urllib.request import urlopen

from prometheus_client.parser import text_string_to_metric_families

from apps.mw.src.config import get_settings
from apps.mw.src.services.stt_queue import STTJob
from apps.mw.src.services.stt_worker import (
    STTWorker,
    TranscriptionResult,
    start_worker_metrics_exporter,
)


class _DummySession:
    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


class _StubQueue:
    def __init__(self, job: STTJob) -> None:
        self._job = job
        self._delivered = False

    def fetch_job(self, *, timeout: int | None = None) -> STTJob | None:
        if self._delivered:
            return None
        self._delivered = True
        return self._job

    def mark_transcribing(self, session: _DummySession, job: STTJob):
        session.commit()
        return object()

    def record_success(
        self,
        session: _DummySession,
        job: STTJob,
        *,
        transcript_path: str,
        language: str | None,
        summary_path: str | None = None,
    ) -> None:
        session.commit()

    def record_failure(self, *args, **kwargs) -> None:  # pragma: no cover - defensive
        raise AssertionError("Failure path should not be triggered in this test")

    def push_to_dlq(self, *args, **kwargs) -> None:  # pragma: no cover - defensive
        raise AssertionError("DLQ path should not be triggered in this test")


class _StubTranscriber:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def transcribe(self, job: STTJob) -> TranscriptionResult:
        target = self._base_dir / f"{job.call_id}.txt"
        target.write_text("ok", encoding="utf-8")
        return TranscriptionResult(transcript_path=str(target), language="en")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_worker_metrics_exporter_reports_success(monkeypatch, tmp_path: Path) -> None:
    port = _find_free_port()
    monkeypatch.setenv("WORKER_METRICS_HOST", "127.0.0.1")
    monkeypatch.setenv("WORKER_METRICS_PORT", str(port))

    get_settings.cache_clear()
    start_worker_metrics_exporter()

    with urlopen(f"http://127.0.0.1:{port}/metrics") as response:
        payload = response.read().decode("utf-8")
    before_metrics = {family.name: family for family in text_string_to_metric_families(payload)}

    queue = _StubQueue(
        STTJob(
            record_id=1,
            call_id="call-1",
            recording_url="https://example.com/audio.wav",
            engine="placeholder",
        )
    )
    transcriber = _StubTranscriber(tmp_path)
    worker = STTWorker(queue, transcriber, session_factory=_DummySession)

    handled = worker.process_next(timeout=0)
    assert handled is True

    with urlopen(f"http://127.0.0.1:{port}/metrics") as response:
        payload = response.read().decode("utf-8")
    after_metrics = {family.name: family for family in text_string_to_metric_families(payload)}

    counter_candidates = ("stt_jobs", "stt_jobs_total")
    success_before = 0.0
    before_counter_family = next(
        (before_metrics[name] for name in counter_candidates if name in before_metrics),
        None,
    )
    if before_counter_family is not None:
        for sample in before_counter_family.samples:
            if sample.labels.get("status") == "success":
                success_before = sample.value
                break

    counter_family = next(
        (after_metrics[name] for name in counter_candidates if name in after_metrics),
        None,
    )
    assert counter_family is not None, f"available metrics: {list(after_metrics)}"
    success_after = 0.0
    for sample in counter_family.samples:
        if sample.labels.get("status") == "success":
            success_after = sample.value
            break

    assert success_after == success_before + 1.0

    duration_before = 0.0
    if "stt_job_duration_seconds" in before_metrics:
        for sample in before_metrics["stt_job_duration_seconds"].samples:
            if sample.name.endswith("_count"):
                duration_before = sample.value
                break

    assert "stt_job_duration_seconds" in after_metrics, f"available metrics: {list(after_metrics)}"
    duration_after = 0.0
    for sample in after_metrics["stt_job_duration_seconds"].samples:
        if sample.name.endswith("_count"):
            duration_after = sample.value
            break

    assert duration_after == duration_before + 1.0

    get_settings.cache_clear()
