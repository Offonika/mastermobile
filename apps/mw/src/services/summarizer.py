"""Utilities for generating Markdown summaries from call transcripts."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Sequence

from loguru import logger

from apps.mw.src.config import Settings, get_settings
from apps.mw.src.services.storage import StorageResult, StorageService

_MIN_BULLETS = 3
_MAX_BULLETS = 5
_MAX_BULLET_LENGTH = 256


@dataclass(slots=True)
class SummaryResult:
    """Structured result of a generated summary."""

    path: str
    bullets: Sequence[str]
    stored: StorageResult


class CallSummarizer:
    """Format transcript text into concise Markdown bullet summaries."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        storage_service: StorageService | None = None,
        timestamp_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._storage = storage_service or StorageService(self._settings)
        self._now = timestamp_provider or (lambda: datetime.now(tz=timezone.utc))

    def summarize(self, call_id: str, transcript_text: str) -> SummaryResult:
        """Generate a Markdown summary and persist it using storage service."""

        bullets = self._build_bullets(transcript_text)
        markdown = self._format_markdown(bullets)
        stored = self._storage.store_summary(
            call_id,
            markdown,
            created_at=self._now(),
        )

        return SummaryResult(path=stored.path, bullets=bullets, stored=stored)

    def _build_bullets(self, transcript_text: str) -> list[str]:
        text = transcript_text.strip()
        if not text:
            raise ValueError("Transcript text is empty; cannot generate summary")

        candidates = self._extract_sentences(text)
        bullets: list[str] = []
        for sentence in candidates:
            cleaned = " ".join(sentence.split())
            if not cleaned:
                continue
            bullets.append(self._truncate(cleaned))
            if len(bullets) >= _MAX_BULLETS:
                break

        if len(bullets) >= _MIN_BULLETS:
            return bullets

        logger.debug(
            "Transcript did not yield enough sentences for summary; using fallback chunks",
        )
        fallback = self._fallback_chunks(text, target=_MIN_BULLETS)
        bullets.extend(self._truncate(chunk) for chunk in fallback)

        # Deduplicate while preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for bullet in bullets:
            if bullet in seen:
                continue
            seen.add(bullet)
            unique.append(bullet)

        if len(unique) < _MIN_BULLETS:
            raise ValueError("Unable to generate enough summary bullets from transcript")

        return unique[:_MAX_BULLETS]

    def _extract_sentences(self, text: str) -> Iterable[str]:
        # Split by line first to preserve operator/customer turns.
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            for sentence in re.split(r"(?<=[.!?])\s+", line):
                sentence = sentence.strip()
                if sentence:
                    yield sentence

    def _fallback_chunks(self, text: str, *, target: int) -> list[str]:
        words = text.split()
        if not words:
            return []

        chunk_size = max(1, math.ceil(len(words) / target))
        chunks: list[str] = []
        for index in range(target):
            start = index * chunk_size
            end = start + chunk_size
            segment_words = words[start:end] if index < target - 1 else words[start:]
            if not segment_words:
                continue
            chunks.append(" ".join(segment_words))
        return chunks

    def _truncate(self, text: str) -> str:
        if len(text) <= _MAX_BULLET_LENGTH:
            return text
        return text[: _MAX_BULLET_LENGTH - 1].rstrip() + "…"

    def _format_markdown(self, bullets: Sequence[str]) -> str:
        lines = [f"- {bullet}" for bullet in bullets]
        return "\n".join(lines) + "\n"


__all__ = ["CallSummarizer", "SummaryResult"]
