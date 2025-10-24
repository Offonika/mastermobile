from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest
import respx
from httpx import Request, Response, codes

from apps.mw.src.config import Settings
from apps.mw.src.services.stt_providers import (
    LocalTranscriptionProvider,
    OpenAIWhisperProvider,
    TranscriptionError,
)
from apps.mw.src.services.stt_queue import STTJob


def _write_sine_wave(path: Path, *, seconds: float = 0.5, sample_rate: int = 16000) -> None:
    amplitude = 0.5
    frequency = 440.0
    total_frames = int(sample_rate * seconds)
    path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for index in range(total_frames):
            sample = amplitude * math.sin(2 * math.pi * frequency * (index / sample_rate))
            value = int(sample * 32767)
            handle.writeframes(struct.pack("<h", value))


@pytest.fixture()
def sample_audio(tmp_path: Path) -> Path:
    path = tmp_path / "sample.wav"
    _write_sine_wave(path)
    return path


@respx.mock
def test_openai_provider_appends_limit_hint_on_error(sample_audio: Path, tmp_path: Path) -> None:
    route = respx.post("https://stt.example/v1/audio/transcriptions").mock(
        return_value=Response(413, json={"error": {"message": "too large"}})
    )
    settings = Settings(
        OPENAI_API_KEY="test-key",
        OPENAI_BASE_URL="https://stt.example/v1",
        STT_ERROR_HINT_413="limit hint",
        STT_MAX_FILE_MINUTES=1,
        STT_MAX_FILE_SIZE_MB=1,
        LOCAL_STORAGE_DIR=str(tmp_path / "storage"),
    )
    provider = OpenAIWhisperProvider(settings=settings, transcripts_dir=tmp_path / "transcripts")
    job = STTJob(
        record_id=1,
        call_id="call-1",
        recording_url=str(sample_audio),
        engine="openai-whisper",
        language="en",
    )

    with pytest.raises(TranscriptionError) as excinfo:
        provider.transcribe(job)

    assert route.called
    assert excinfo.value.status_code == 413
    message = str(excinfo.value)
    assert "limit hint" in message
    assert "1" in message


@respx.mock
def test_local_provider_sends_authorization_and_persists_transcript(
    sample_audio: Path, tmp_path: Path
) -> None:
    captured_headers: dict[str, str] = {}

    def responder(request: Request) -> Response:
        captured_headers.update(request.headers)
        return Response(200, json={"text": "тестовый текст", "language": "ru"})

    respx.post("https://local-stt/transcribe").mock(side_effect=responder)

    settings = Settings(
        LOCAL_STT_URL="https://local-stt/transcribe",
        LOCAL_STT_API_KEY="secret-token",
        LOCAL_STORAGE_DIR=str(tmp_path / "storage"),
    )
    provider = LocalTranscriptionProvider(settings=settings, transcripts_dir=tmp_path / "transcripts")
    job = STTJob(
        record_id=42,
        call_id="call-ru",
        recording_url=str(sample_audio),
        engine="local",
        language="ru",
    )

    result = provider.transcribe(job)

    normalized_headers = {key.lower(): value for key, value in captured_headers.items()}
    assert normalized_headers.get("authorization") == "Bearer secret-token"
    transcript_file = Path(result.transcript_path)
    assert transcript_file.exists()
    assert transcript_file.read_text(encoding="utf-8").strip() == "тестовый текст"
    assert result.language == "ru"


def test_local_provider_validates_duration_limit(tmp_path: Path) -> None:
    long_audio = tmp_path / "long.wav"
    _write_sine_wave(long_audio, seconds=40.0)

    settings = Settings(
        LOCAL_STT_URL="https://local-stt/transcribe",
        LOCAL_STORAGE_DIR=str(tmp_path / "storage"),
        STT_MAX_FILE_SIZE_MB=1,
    )
    provider = LocalTranscriptionProvider(settings=settings, transcripts_dir=tmp_path / "transcripts")
    job = STTJob(
        record_id=2,
        call_id="call-long",
        recording_url=str(long_audio),
        engine="local",
    )

    with pytest.raises(TranscriptionError) as excinfo:
        provider.transcribe(job)

    assert excinfo.value.status_code == codes.REQUEST_ENTITY_TOO_LARGE
