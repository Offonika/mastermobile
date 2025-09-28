#!/usr/bin/env python3
"""Validate 1C dump/external processor assets against the manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / '1c' / 'verification_manifest.json'


class VerificationError(RuntimeError):
    """Represents a validation failure."""


def compute_sha256(path: Path) -> str:
    """Compute the SHA-256 hash of ``path``."""
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(base_path: Path) -> Iterable[Path]:
    for file_path in sorted(base_path.rglob('*')):
        if file_path.is_file():
            yield file_path


def validate_tree(name: str, base_path: Path, expected: Dict[str, Dict[str, object]], *, allow_extra: bool) -> None:
    if not base_path.exists():
        raise VerificationError(f"Missing directory for '{name}': {base_path}")

    expected_paths = {Path(relative) for relative in expected.keys()}
    actual_paths = {path.relative_to(base_path) for path in iter_files(base_path)}

    missing = sorted(str(path) for path in expected_paths - actual_paths)
    if missing:
        raise VerificationError(
            f"'{name}' is missing required files: {', '.join(missing)}"
        )

    if not allow_extra:
        extras = sorted(str(path) for path in actual_paths - expected_paths)
        if extras:
            raise VerificationError(
                f"'{name}' contains unexpected files: {', '.join(extras)}"
            )

    for relative, metadata in expected.items():
        rel_path = Path(relative)
        target = base_path / rel_path
        if not target.is_file():
            raise VerificationError(f"Expected file not found for '{name}': {target}")

        size = target.stat().st_size
        expected_size = metadata.get('size')
        if expected_size is None:
            raise VerificationError(f"Manifest for '{name}' lacks size for {relative}")
        if size != expected_size:
            raise VerificationError(
                f"Size mismatch for '{name}'/{relative}: expected {expected_size}, actual {size}"
            )

        expected_hash = metadata.get('sha256')
        if not expected_hash:
            raise VerificationError(f"Manifest for '{name}' lacks sha256 for {relative}")
        actual_hash = compute_sha256(target)
        if actual_hash.lower() != str(expected_hash).lower():
            raise VerificationError(
                f"Hash mismatch for '{name}'/{relative}: expected {expected_hash}, actual {actual_hash}"
            )


def load_manifest(path: Path) -> Dict[str, Dict[str, object]]:
    if not path.exists():
        raise VerificationError(f'Manifest not found: {path}')

    with path.open('r', encoding='utf-8') as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise VerificationError(f'Invalid JSON manifest: {exc}') from exc

    if not isinstance(data, dict):
        raise VerificationError('Manifest root must be an object')
    return data


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--manifest',
        type=Path,
        default=DEFAULT_MANIFEST,
        help='Path to the verification manifest (default: %(default)s)',
    )
    parser.add_argument(
        '--allow-extra-files',
        action='store_true',
        help='Do not fail if extra files are present alongside the required ones.',
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    try:
        args = parse_args(argv)
        manifest = load_manifest(args.manifest)

        for key, entry in manifest.items():
            if not isinstance(entry, dict):
                raise VerificationError(f"Manifest section '{key}' must be an object")
            base_path_value = entry.get('base_path')
            if not isinstance(base_path_value, str):
                raise VerificationError(f"Manifest section '{key}' missing base_path")
            files = entry.get('files')
            if not isinstance(files, dict) or not files:
                raise VerificationError(f"Manifest section '{key}' has no files to validate")

            base_path = (REPO_ROOT / base_path_value).resolve()
            validate_tree(key, base_path, files, allow_extra=args.allow_extra_files)
            print(f"✔ Verified {key} ({len(files)} files)")
    except VerificationError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - safety net for unexpected issues
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
