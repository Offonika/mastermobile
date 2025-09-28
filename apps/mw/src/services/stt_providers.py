"""Speech-to-text provider implementations and helpers."""
from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import urlparse

import httpx
from imageio_ffmpeg import get_ffmpeg_exe
from loguru import logger

from apps.mw.src.config import Settings, get_settings
from apps.mw.src.services.stt_queue import STTJob


ENGINE_STUB = "stub"
ENGINE_OPENAI = "openai-whisper"
ENGINE_LOCAL = "local"

_TRANSCRIPTS_SUBDIR = "transcripts"


@dataclass(slots=True)
class TranscriptionResult:
    """Successful transcription metadata."""

    transcript_path: str
    language: str | None = None


class SpeechToTextProvider(Protocol):
    """Protocol implemented by speech-to-text providers."""

    def transcribe(self, job: STTJob) -> TranscriptionResult:  # pragma: no cover - Protocol
        """Process an STT job and return metadata about the transcript."""


class TranscriptionError(Exception):
    """Raised when a transcription attempt failed."""

    def __init__(self, status_code: int | None, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _default_transcripts_dir(settings: Settings) -> Path:
    root = Path(settings.local_storage_dir)
    return root / _TRANSCRIPTS_SUBDIR


def _sanitise_call_id(call_id: str) -> str:
    clean = [ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in call_id]
    stem = "".join(clean).strip("._")
    return stem or "transcript"


def _download_recording(recording_url: str, destination_dir: Path, *, timeout: float) -> Path:
    parsed = urlparse(recording_url)

    if parsed.scheme in {"", "file"}:
        source_path = Path(parsed.path if parsed.scheme else recording_url)
        if not source_path.exists():
            raise TranscriptionError(None, f"Recording not found at {recording_url}")
        destination = destination_dir / (source_path.name or "recording")
        if source_path.resolve() != destination.resolve():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, destination)
        return destination

    if parsed.scheme in {"http", "https"}:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(recording_url)
            if response.status_code != httpx.codes.OK:
                message = _extract_error_message(response)
                raise TranscriptionError(response.status_code, message or "Unable to download recording")
            filename = Path(parsed.path).name or "recording"
            destination = destination_dir / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)
            return destination

    raise TranscriptionError(None, f"Unsupported recording URL scheme: {parsed.scheme}")


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text.strip()

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
        message = payload.get("message")
        if isinstance(message, str):
            return message
    return ""


def _convert_to_wav_mono16k(source_path: Path, target_path: Path) -> float:
    ffmpeg_path = get_ffmpeg_exe()
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(source_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(target_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.bind(
            source=str(source_path),
            returncode=result.returncode,
            stderr=result.stderr,
        ).error("Failed to convert audio to wav mono 16k")
        raise TranscriptionError(None, "Audio conversion failed")

    with contextlib.closing(wave.open(str(target_path), "rb")) as wav_file:  # type: ignore[name-defined]
        frames = wav_file.getnframes()
        frame_rate = wav_file.getframerate() or 1
    duration_seconds = frames / float(frame_rate)
    return duration_seconds


def _ensure_limits(settings: Settings, *, duration_seconds: float, file_size: int) -> None:
    max_minutes = settings.stt_max_file_minutes
    if max_minutes and duration_seconds > max_minutes * 60:
        raise TranscriptionError(
            httpx.codes.REQUEST_ENTITY_TOO_LARGE,
            (
                "Recording duration exceeds configured limit: "
                f"{duration_seconds / 60:.1f} min > {max_minutes} min"
            ),
        )

    max_bytes = settings.stt_max_file_size_mb
    if max_bytes and file_size > max_bytes * 1024 * 1024:
        size_mb = file_size / (1024 * 1024)
        raise TranscriptionError(
            httpx.codes.REQUEST_ENTITY_TOO_LARGE,
            f"Recording size {size_mb:.1f} MB exceeds {max_bytes} MB limit",
        )


def _prepare_transcript_path(transcripts_dir: Path, call_id: str) -> Path:
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_sanitise_call_id(call_id)}.txt"
    return transcripts_dir / filename


class PlaceholderTranscriber:
    """A minimal local transcriber used until a real backend is wired in."""

    def __init__(self, transcripts_dir: Path) -> None:
        self._transcripts_dir = transcripts_dir

    def transcribe(self, job: STTJob) -> TranscriptionResult:
        path = _prepare_transcript_path(self._transcripts_dir, job.call_id)
        if not path.exists():
            path.write_text(
                "Transcription placeholder. Configure a real STT provider to replace this output.\n",
                encoding="utf-8",
            )
        return TranscriptionResult(transcript_path=str(path), language=job.language)


class _BaseHttpProvider:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transcripts_dir: Path | None = None,
        http_client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._transcripts_dir = transcripts_dir or _default_transcripts_dir(self._settings)
        self._http_client_factory = http_client_factory or self._default_http_client_factory

    def _default_http_client_factory(self) -> httpx.Client:
        return httpx.Client(timeout=float(self._settings.request_timeout_s))

    def _build_http_client(self) -> httpx.Client:
        client = self._http_client_factory()
        if not isinstance(client, httpx.Client):  # pragma: no cover - defensive
            raise TypeError("HTTP client factory must return httpx.Client")
        return client

    def _append_limit_hint(self, status_code: int, message: str) -> str:
        hint = None
        if status_code == httpx.codes.REQUEST_ENTITY_TOO_LARGE:
            hint = self._settings.stt_error_hint_413
            details: list[str] = []
            if self._settings.stt_max_file_minutes:
                details.append(f"макс. длительность {self._settings.stt_max_file_minutes} мин")
            if self._settings.stt_max_file_size_mb:
                details.append(f"размер до {self._settings.stt_max_file_size_mb} МБ")
            if details:
                hint = f"{hint} ({', '.join(details)})"
        elif status_code == httpx.codes.UNPROCESSABLE_ENTITY:
            hint = self._settings.stt_error_hint_422

        if hint:
            return f"{message}. {hint}" if message else hint
        return message

    def _handle_response_error(self, response: httpx.Response) -> None:
        message = _extract_error_message(response)
        message = self._append_limit_hint(response.status_code, message)
        raise TranscriptionError(response.status_code, message or "STT provider error")

    def _download(self, job: STTJob, temp_dir: Path) -> Path:
        timeout = float(self._settings.request_timeout_s)
        return _download_recording(job.recording_url, temp_dir, timeout=timeout)


class OpenAIWhisperProvider(_BaseHttpProvider):
    """Provider that uploads audio to the OpenAI Whisper transcription API."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transcripts_dir: Path | None = None,
        http_client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        super().__init__(
            settings=settings,
            transcripts_dir=transcripts_dir,
            http_client_factory=http_client_factory,
        )
        if not self._settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be configured to use OpenAI Whisper provider")

    def transcribe(self, job: STTJob) -> TranscriptionResult:
        language = job.language or self._settings.stt_default_language
        transcripts_dir = self._transcripts_dir

        with tempfile.TemporaryDirectory(prefix="stt-openai-") as temp_root:
            temp_dir = Path(temp_root)
            source_path = self._download(job, temp_dir)
            wav_path = temp_dir / "converted.wav"
            duration_seconds = _convert_to_wav_mono16k(source_path, wav_path)
            _ensure_limits(
                self._settings,
                duration_seconds=duration_seconds,
                file_size=wav_path.stat().st_size,
            )

            url = f"{self._settings.openai_base_url.rstrip('/')}/audio/transcriptions"
            data: dict[str, str] = {"model": self._settings.stt_openai_model}
            if language:
                data["language"] = language

            headers = {"Authorization": f"Bearer {self._settings.openai_api_key}"}

            client = self._build_http_client()
            try:
                files = {"file": (f"{job.call_id}.wav", wav_path.read_bytes(), "audio/wav")}
                response = client.post(url, data=data, files=files, headers=headers)
            finally:
                client.close()

            if response.status_code != httpx.codes.OK:
                self._handle_response_error(response)

            try:
                payload = response.json()
            except json.JSONDecodeError as exc:
                raise TranscriptionError(None, "Unexpected response from OpenAI Whisper") from exc

            text = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(text, str):
                raise TranscriptionError(None, "OpenAI Whisper response is missing transcript text")

            detected_language = payload.get("language") if isinstance(payload, dict) else None
            transcript_path = _prepare_transcript_path(transcripts_dir, job.call_id)
            transcript_path.write_text(text.strip() + "\n", encoding="utf-8")

            return TranscriptionResult(
                transcript_path=str(transcript_path),
                language=str(detected_language) if isinstance(detected_language, str) else language,
            )


class LocalTranscriptionProvider(_BaseHttpProvider):
    """Provider that forwards audio to a local HTTP backend."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transcripts_dir: Path | None = None,
        http_client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        super().__init__(
            settings=settings,
            transcripts_dir=transcripts_dir,
            http_client_factory=http_client_factory,
        )
        if not self._settings.local_stt_url:
            raise ValueError("LOCAL_STT_URL must be configured to use the local STT provider")

    def transcribe(self, job: STTJob) -> TranscriptionResult:
        language = job.language or self._settings.stt_default_language
        transcripts_dir = self._transcripts_dir

        with tempfile.TemporaryDirectory(prefix="stt-local-") as temp_root:
            temp_dir = Path(temp_root)
            source_path = self._download(job, temp_dir)
            wav_path = temp_dir / "converted.wav"
            duration_seconds = _convert_to_wav_mono16k(source_path, wav_path)
            _ensure_limits(
                self._settings,
                duration_seconds=duration_seconds,
                file_size=wav_path.stat().st_size,
            )

            data: dict[str, str] = {}
            if language:
                data["language"] = language

            headers = {}
            if self._settings.local_stt_api_key:
                headers["Authorization"] = f"Bearer {self._settings.local_stt_api_key}"

            client = self._build_http_client()
            try:
                files = {"file": (f"{job.call_id}.wav", wav_path.read_bytes(), "audio/wav")}
                response = client.post(self._settings.local_stt_url, data=data, files=files, headers=headers)
            finally:
                client.close()

            if response.status_code != httpx.codes.OK:
                self._handle_response_error(response)

            try:
                payload = response.json()
            except json.JSONDecodeError as exc:
                raise TranscriptionError(None, "Unexpected response from local STT backend") from exc

            text = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(text, str):
                raise TranscriptionError(None, "Local STT response is missing transcript text")

            detected_language = payload.get("language") if isinstance(payload, dict) else None
            transcript_path = _prepare_transcript_path(transcripts_dir, job.call_id)
            transcript_path.write_text(text.strip() + "\n", encoding="utf-8")

            return TranscriptionResult(
                transcript_path=str(transcript_path),
                language=str(detected_language) if isinstance(detected_language, str) else language,
            )


class ProviderRouter(SpeechToTextProvider):
    """Dispatch STT jobs to configured providers based on the requested engine."""

    def __init__(self, settings: Settings | None = None, *, transcripts_dir: Path | None = None) -> None:
        self._settings = settings or get_settings()
        transcripts_dir = transcripts_dir or _default_transcripts_dir(self._settings)

        providers: dict[str, SpeechToTextProvider] = {}
        providers[ENGINE_STUB] = PlaceholderTranscriber(transcripts_dir)

        if self._settings.stt_openai_enabled:
            try:
                providers[ENGINE_OPENAI] = OpenAIWhisperProvider(
                    settings=self._settings,
                    transcripts_dir=transcripts_dir,
                )
            except ValueError as exc:
                logger.warning("Skipping OpenAI Whisper provider: {}", exc)

        if self._settings.stt_local_enabled:
            try:
                providers[ENGINE_LOCAL] = LocalTranscriptionProvider(
                    settings=self._settings,
                    transcripts_dir=transcripts_dir,
                )
            except ValueError as exc:
                logger.warning("Skipping local STT provider: {}", exc)

        self._providers = providers
        self._default_engine = self._settings.stt_default_engine or ENGINE_STUB

    def transcribe(self, job: STTJob) -> TranscriptionResult:
        engine = job.engine or self._default_engine
        provider = self._providers.get(engine)
        if provider is None:
            raise TranscriptionError(None, f"STT engine '{engine}' is not enabled")
        return provider.transcribe(job)


__all__ = [
    "ENGINE_LOCAL",
    "ENGINE_OPENAI",
    "ENGINE_STUB",
    "LocalTranscriptionProvider",
    "OpenAIWhisperProvider",
    "PlaceholderTranscriber",
    "ProviderRouter",
    "SpeechToTextProvider",
    "TranscriptionError",
    "TranscriptionResult",
]
