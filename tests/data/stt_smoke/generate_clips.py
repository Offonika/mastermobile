#!/usr/bin/env python3
"""Generate synthetic speech fixtures for STT smoke tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

MANIFEST_PATH = Path(__file__).with_name("manifest.json")
OUTPUT_DIR = MANIFEST_PATH.parent


def load_manifest() -> dict:
    try:
        with MANIFEST_PATH.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise SystemExit(f"Manifest not found: {MANIFEST_PATH}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        raise SystemExit(f"Manifest is not valid JSON: {exc}") from exc


def iter_clips(selected: Iterable[str] | None = None) -> list[dict]:
    manifest = load_manifest()
    clips = manifest.get("clips", [])
    if selected:
        index = {clip["filename"]: clip for clip in clips}
        missing = sorted(set(selected) - set(index))
        if missing:
            raise SystemExit(
                "Unknown clip(s) requested: " + ", ".join(missing)
            )
        return [index[name] for name in selected]
    return clips


def ensure_dependencies() -> None:
    try:
        import gtts  # noqa: F401
    except ImportError as exc:  # pragma: no cover - deterministic failure path
        raise SystemExit(
            "Missing dependency 'gTTS'. Install with 'pip install gTTS>=2.5.4'."
        ) from exc


def synthesize_clip(clip: dict, force: bool = False) -> Path:
    ensure_dependencies()
    from gtts import gTTS  # type: ignore

    target = OUTPUT_DIR / clip["filename"]
    if target.exists() and not force:
        print(f"Skipping {target.name} (already exists)")
        return target

    print(f"Generating {target.name} → {target}")
    tts = gTTS(text=clip["text"], lang=clip["language"])
    tts.save(str(target))
    validate_checksum(target, clip.get("sha256"))
    return target


def validate_checksum(path: Path, expected: str | None) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8192), b""):
            digest.update(chunk)
    checksum = digest.hexdigest()
    if expected and checksum != expected:
        path.unlink(missing_ok=True)
        raise SystemExit(
            f"Checksum mismatch for {path.name}: expected {expected}, got {checksum}."
        )
    if expected:
        print(f"Verified checksum for {path.name}: {checksum}")
    else:
        print(f"Checksum for {path.name}: {checksum}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate speech fixtures defined in manifest.json",
    )
    parser.add_argument(
        "filenames",
        nargs="*",
        help="Optional list of filenames to generate. Defaults to all clips.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files instead of skipping them.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    clips = iter_clips(args.filenames or None)
    for clip in clips:
        synthesize_clip(clip, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
