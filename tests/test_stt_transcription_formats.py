from __future__ import annotations

import math
import struct
import subprocess
import wave
from collections.abc import Iterable
from pathlib import Path

import httpx
import respx
from imageio_ffmpeg import get_ffmpeg_exe

from apps.mw.src.config import Settings
from apps.mw.src.services.stt_providers import ENGINE_OPENAI, ProviderRouter
from apps.mw.src.services.stt_queue import STTJob


def _write_sine_wave(path: Path, *, seconds: float = 0.5, sample_rate: int = 22050) -> None:
    amplitude = 0.5
    frequency = 220.0
    total_frames = int(sample_rate * seconds)
    path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for index in range(total_frames):
            value = amplitude * math.sin(2 * math.pi * frequency * (index / sample_rate))
            handle.writeframes(struct.pack("<h", int(value * 32767)))


def _encode_with_ffmpeg(source: Path, target: Path, *, codec_args: Iterable[str] | None = None) -> None:
    command = [get_ffmpeg_exe(), "-y", "-i", str(source), "-ac", "1"]
    if codec_args:
        command.extend(codec_args)
    command.append(str(target))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:  # pragma: no cover - defensive guard
        raise RuntimeError(result.stderr)


@respx.mock
def test_provider_router_transcribes_multiple_formats(tmp_path: Path) -> None:
    base_audio = tmp_path / "fixtures" / "base.wav"
    _write_sine_wave(base_audio)

    playlist = {
        "wav": base_audio,
        "flac": tmp_path / "fixtures" / "sample.flac",
        "m4a": tmp_path / "fixtures" / "sample.m4a",
    }

    _encode_with_ffmpeg(base_audio, playlist["flac"])
    _encode_with_ffmpeg(base_audio, playlist["m4a"], codec_args=["-c:a", "aac", "-b:a", "64k"])

    responses = iter(
        [
            httpx.Response(200, json={"text": "Transcript wav", "language": "en"}),
            httpx.Response(200, json={"text": "Transcript flac", "language": "en"}),
            httpx.Response(200, json={"text": "Transcript m4a", "language": "en"}),
        ]
    )

    respx.post("https://api.test/v1/audio/transcriptions").mock(side_effect=lambda _: next(responses))

    settings = Settings(
        OPENAI_API_KEY="token",
        OPENAI_BASE_URL="https://api.test/v1",
        LOCAL_STORAGE_DIR=str(tmp_path / "storage"),
        STT_OPENAI_ENABLED=True,
        STT_DEFAULT_ENGINE=ENGINE_OPENAI,
        STT_DEFAULT_LANGUAGE="en",
        STT_MAX_FILE_SIZE_MB=10,
    )

    router = ProviderRouter(settings=settings, transcripts_dir=tmp_path / "transcripts")

    for format_name, source in playlist.items():
        job = STTJob(
            record_id=1,
            call_id=f"job-{format_name}",
            recording_url=str(source),
            engine=ENGINE_OPENAI,
            language="en",
        )
        result = router.transcribe(job)
        transcript_path = Path(result.transcript_path)
        assert transcript_path.exists()
        content = transcript_path.read_text(encoding="utf-8").strip()
        assert content.endswith(format_name)

    assert respx.calls.call_count == len(playlist)
