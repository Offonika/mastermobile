#!/usr/bin/env python3
"""Smoke-test utility for speech-to-text providers."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.mw.src.config import Settings, get_settings
from apps.mw.src.services.stt_queue import STTJob

try:  # pragma: no cover - import wiring depends on optional dependencies
    from apps.mw.src.services.stt_worker import (
        PlaceholderTranscriber as WorkerPlaceholderTranscriber,
        SpeechToTextProvider as WorkerSpeechToTextProvider,
        TranscriptionError as WorkerTranscriptionError,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - fallback for optional deps
    if exc.name != "prometheus_client":
        raise

    @dataclass(slots=True)
    class TranscriptionResult:
        transcript_path: str
        language: str | None = None

    class TranscriptionError(Exception):
        """Raised when a transcription attempt failed."""

        def __init__(self, status_code: int | None, message: str) -> None:
            super().__init__(message)
            self.status_code = status_code

    class SpeechToTextProvider(Protocol):
        """Simplified protocol for providers."""

        def transcribe(self, job: Any) -> TranscriptionResult:  # pragma: no cover - protocol definition
            ...

    class PlaceholderTranscriber:
        """Local re-implementation of the default placeholder transcriber."""

        def __init__(self, transcripts_dir: Path) -> None:
            self._transcripts_dir = transcripts_dir

        def transcribe(self, job: Any) -> TranscriptionResult:
            self._transcripts_dir.mkdir(parents=True, exist_ok=True)
            target = self._transcripts_dir / f"{job.call_id}.txt"
            if not target.exists():
                target.write_text(
                    "Transcription placeholder. Configure a real STT provider to replace this output.\n",
                    encoding="utf-8",
                )
            return TranscriptionResult(transcript_path=str(target), language=getattr(job, "language", None))

else:  # pragma: no cover - main path when optional deps available

    TranscriptionError = WorkerTranscriptionError
    SpeechToTextProvider = WorkerSpeechToTextProvider
    PlaceholderTranscriber = WorkerPlaceholderTranscriber

DEFAULT_PATTERNS = ("*.wav", "*.mp3", "*.m4a", "*.flac", "*.ogg")
DEFAULT_REPORT_BASENAME = "stt_smoke_report"


@dataclass(slots=True)
class FileReport:
    """Per-file transcription metadata persisted in the final report."""

    source_file: str
    status: str
    duration_seconds: float
    transcript_path: str | None
    error: str | None
    language: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""

        payload = asdict(self)
        # Keep durations rounded for readability but preserve numeric type.
        payload["duration_seconds"] = round(self.duration_seconds, 4)
        return payload


def build_transcriber(settings: Settings) -> SpeechToTextProvider:
    """Return the STT provider instance based on configuration."""

    transcripts_dir = Path(settings.local_storage_dir) / "transcripts"
    return PlaceholderTranscriber(transcripts_dir)


def gather_playlist(playlist_dir: Path, patterns: Iterable[str]) -> list[Path]:
    """Return an ordered list of audio files matching the provided patterns."""

    if not patterns:
        files = [path for path in sorted(playlist_dir.rglob("*")) if path.is_file()]
    else:
        ordered: dict[Path, None] = {}
        for pattern in patterns:
            for path in sorted(playlist_dir.rglob(pattern)):
                if path.is_file():
                    ordered.setdefault(path, None)
        files = list(ordered.keys())

    return files


def transcribe_files(
    files: Sequence[Path],
    *,
    base_dir: Path,
    transcriber: SpeechToTextProvider,
    engine: str,
    language: str | None,
) -> list[FileReport]:
    """Transcribe every file and capture timings."""

    reports: list[FileReport] = []
    for index, path in enumerate(files, start=1):
        absolute_path = path.resolve()
        start = perf_counter()
        transcript_path: str | None = None
        error: str | None = None
        status = "success"

        try:
            job = STTJob(
                record_id=index,
                call_id=absolute_path.stem,
                recording_url=absolute_path.as_uri(),
                engine=engine,
                language=language,
            )
            result = transcriber.transcribe(job)
            transcript_path = result.transcript_path
        except TranscriptionError as exc:
            status = "error"
            error = f"TranscriptionError[{exc.status_code}]: {exc}"
        except Exception as exc:  # pragma: no cover - defensive guard for unexpected errors
            status = "error"
            error = f"Unexpected error: {exc}"

        duration = perf_counter() - start
        try:
            source_display = str(absolute_path.relative_to(base_dir))
        except ValueError:  # pragma: no cover - defensive fallback when paths mismatch
            source_display = str(absolute_path)

        reports.append(
            FileReport(
                source_file=source_display,
                status=status,
                duration_seconds=duration,
                transcript_path=transcript_path,
                error=error,
                language=language,
            )
        )

    return reports


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    """Persist the JSON report to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown_report(path: Path, payload: dict[str, Any], rows: Sequence[FileReport]) -> None:
    """Persist a Markdown summary report to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "# STT Smoke Test Report",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Playlist directory: `{payload['playlist_dir']}`",
        f"- Engine: `{payload['engine']}`",
        f"- File patterns: {', '.join(payload['patterns']) if payload['patterns'] else 'all files'}",
        f"- Total files: {payload['total_files']}",
        f"- Success: {payload['success_count']}",
        f"- Errors: {payload['error_count']}",
        "",
        "| File | Status | Duration (s) | Transcript | Error |",
        "| --- | --- | --- | --- | --- |",
    ]

    def format_status(item: FileReport) -> str:
        return "✅ Success" if item.status == "success" else "❌ Error"

    def format_duration(item: FileReport) -> str:
        return f"{item.duration_seconds:.2f}"

    def format_transcript(item: FileReport) -> str:
        if item.transcript_path:
            return f"`{item.transcript_path}`"
        return ""

    def format_error(item: FileReport) -> str:
        return item.error or ""

    rows_content = [
        "| "
        + " | ".join(
            [
                f"`{Path(report.source_file).name}`",
                format_status(report),
                format_duration(report),
                format_transcript(report),
                format_error(report),
            ]
        )
        + " |"
        for report in rows
    ]

    path.write_text("\n".join(header + rows_content) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""

    parser = argparse.ArgumentParser(description="Run a speech-to-text smoke test on a playlist directory.")
    parser.add_argument(
        "--playlist",
        type=Path,
        required=True,
        help="Path to the directory that contains audio files to transcribe.",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        help="Glob pattern(s) (e.g. *.wav) used to filter files. Defaults to common audio formats.",
    )
    parser.add_argument(
        "--engine",
        default="placeholder",
        help="Engine name to record in the report (does not change provider implementation yet).",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Optional language hint passed to the provider.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports"),
        help="Directory where JSON and Markdown reports will be written.",
    )
    parser.add_argument(
        "--report-name",
        default=DEFAULT_REPORT_BASENAME,
        help="Base name (without extension) for the report files.",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        default=None,
        help="Explicit path to the JSON report. Overrides --report-dir/--report-name when provided.",
    )
    parser.add_argument(
        "--markdown-report",
        type=Path,
        default=None,
        help="Explicit path to the Markdown report. Overrides --report-dir/--report-name when provided.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the smoke-test runner."""

    parser = build_parser()
    args = parser.parse_args(argv)

    playlist_dir: Path = args.playlist
    if not playlist_dir.exists() or not playlist_dir.is_dir():
        parser.error(f"Playlist directory does not exist or is not a directory: {playlist_dir}")
    playlist_dir = playlist_dir.resolve()

    patterns: list[str] = args.patterns or list(DEFAULT_PATTERNS)

    settings = get_settings()
    transcriber = build_transcriber(settings)

    files = gather_playlist(playlist_dir, patterns)
    if not files:
        parser.error(f"No files matched the provided patterns in {playlist_dir}")

    reports = transcribe_files(
        files,
        base_dir=playlist_dir,
        transcriber=transcriber,
        engine=args.engine,
        language=args.language,
    )

    success_count = sum(1 for report in reports if report.status == "success")
    error_count = len(reports) - success_count

    generated_at = datetime.now(tz=UTC).isoformat()
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "playlist_dir": str(playlist_dir.resolve()),
        "patterns": patterns,
        "engine": args.engine,
        "language": args.language,
        "total_files": len(reports),
        "success_count": success_count,
        "error_count": error_count,
        "results": [report.to_dict() for report in reports],
    }

    report_dir: Path = args.report_dir
    base_name: str = args.report_name
    json_path = args.json_report or (report_dir / f"{base_name}.json")
    markdown_path = args.markdown_report or (report_dir / f"{base_name}.md")

    write_json_report(json_path, payload)
    write_markdown_report(markdown_path, payload, reports)

    print(f"Processed {len(reports)} file(s). Success: {success_count}, errors: {error_count}.")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":  # pragma: no cover - script entry point
    raise SystemExit(main())
