"""Data access helpers for Bitrix24 call transcripts."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from apps.mw.src.db.models import B24Transcript


@dataclass(slots=True)
class B24TranscriptSearchResult:
    """Search match returned by :class:`B24TranscriptRepository`."""

    transcript: B24Transcript
    snippet: str
    score: float | None = None


class B24TranscriptRepository:
    """CRUD helpers around the :class:`~apps.mw.src.db.models.B24Transcript` model."""

    _HIGHLIGHT_OPTIONS = "StartSel=<mark>,StopSel=</mark>,MaxFragments=1,ShortWord=2,MaxWords=30"

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        call_record_id: int,
        text_full: str,
        text_normalized: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> B24Transcript:
        """Persist a new transcript for the given call record."""

        transcript = B24Transcript(
            call_record_id=call_record_id,
            text_full=text_full,
            text_normalized=text_normalized,
            metadata_json=metadata,
        )
        self._session.add(transcript)
        self._session.flush()
        return transcript

    def get_by_call_record_id(self, call_record_id: int) -> B24Transcript | None:
        """Return a transcript bound to the provided call record, if any."""

        statement: Select[tuple[B24Transcript]] = select(B24Transcript).where(
            B24Transcript.call_record_id == call_record_id
        )
        return self._session.scalar(statement)

    def update(
        self,
        transcript: B24Transcript,
        *,
        text_full: str | None = None,
        text_normalized: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> B24Transcript:
        """Update text fields or metadata on an existing transcript."""

        if text_full is not None:
            transcript.text_full = text_full
        if text_normalized is not None:
            transcript.text_normalized = text_normalized
        if metadata is not None:
            transcript.metadata_json = metadata
        self._session.flush()
        return transcript

    def delete(self, transcript: B24Transcript) -> None:
        """Remove a transcript and flush the session immediately."""

        self._session.delete(transcript)
        self._session.flush()

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[B24TranscriptSearchResult]:
        """Search transcripts using PostgreSQL FTS or a lightweight fallback."""

        terms = [part for part in query.split() if part]
        if not terms or limit <= 0 or offset < 0:
            return []

        bind = self._session.get_bind()
        if bind.dialect.name == "postgresql":
            return self._search_postgres(" ".join(terms), limit=limit, offset=offset)
        return self._search_fallback(terms, limit=limit, offset=offset)

    def _search_postgres(self, query: str, *, limit: int, offset: int) -> list[B24TranscriptSearchResult]:
        ts_query = func.websearch_to_tsquery("russian", query)
        vector = func.to_tsvector("russian", B24Transcript.text_full)
        rank = func.ts_rank_cd(vector, ts_query)
        headline = func.ts_headline(
            "russian",
            B24Transcript.text_full,
            ts_query,
            self._HIGHLIGHT_OPTIONS,
        )

        statement: Select[tuple[B24Transcript, str, float]] = (
            select(B24Transcript, headline.label("snippet"), rank.label("score"))
            .where(vector.op("@@")(ts_query))
            .order_by(text("score DESC"))
            .limit(limit)
            .offset(offset)
        )
        rows = self._session.execute(statement).all()
        results: list[B24TranscriptSearchResult] = []
        for transcript, snippet, score in rows:
            results.append(
                B24TranscriptSearchResult(
                    transcript=transcript,
                    snippet=snippet or "",
                    score=float(score) if score is not None else None,
                )
            )
        return results

    def _search_fallback(
        self,
        terms: list[str],
        *,
        limit: int,
        offset: int,
    ) -> list[B24TranscriptSearchResult]:
        lowered_terms = [term.casefold() for term in terms]
        statement: Select[tuple[B24Transcript]] = select(B24Transcript).order_by(
            B24Transcript.call_record_id
        )
        transcripts = self._session.scalars(statement).all()
        filtered = [t for t in transcripts if _contains_terms(t.text_full, lowered_terms)]
        sliced = filtered[offset : offset + limit]
        results: list[B24TranscriptSearchResult] = []
        for transcript in sliced:
            snippet = _build_fallback_snippet(transcript.text_full, lowered_terms)
            results.append(B24TranscriptSearchResult(transcript=transcript, snippet=snippet))
        return results


def _contains_terms(text: str, lowered_terms: list[str]) -> bool:
    haystack = " ".join(text.split()).casefold()
    return all(term in haystack for term in lowered_terms)


def _build_fallback_snippet(text: str, lowered_terms: list[str], *, context: int = 60) -> str:
    """Produce a highlighted snippet for non-PostgreSQL databases."""

    compact = " ".join(text.split())
    lowered = compact.casefold()

    match_index: int | None = None
    match_length: int = 0
    for term in lowered_terms:
        idx = lowered.find(term)
        if idx == -1:
            continue
        if match_index is None or idx < match_index:
            match_index = idx
            match_length = len(term)
    if match_index is None:
        if len(compact) <= context * 2:
            return compact
        return compact[: context * 2].rstrip() + "…"

    start = max(0, match_index - context)
    end = min(len(compact), match_index + match_length + context)
    snippet = compact[start:end]

    highlight_start = match_index - start
    highlight_end = highlight_start + match_length
    snippet = (
        snippet[:highlight_start]
        + "<mark>"
        + snippet[highlight_start:highlight_end]
        + "</mark>"
        + snippet[highlight_end:]
    )

    if start > 0:
        snippet = "…" + snippet
    if end < len(compact):
        snippet = snippet + "…"
    return snippet
