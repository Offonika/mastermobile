from __future__ import annotations

from typing import Iterator

import pytest
from sqlalchemy.orm import Session

from apps.mw.src.db.repositories.transcripts import B24TranscriptRepository
from tests.transcript_test_utils import make_call_record, transcript_session


@pytest.fixture()
def session() -> Iterator[Session]:
    with transcript_session() as session:
        yield session


def test_search_returns_snippet_with_highlight(session: Session) -> None:
    record = make_call_record(session, call_id="CALL-001")
    repo = B24TranscriptRepository(session)
    repo.create(
        call_record_id=record.id,
        text_full="Менеджер оформляет возврат телефона и уточняет условия оплаты клиента.",
    )

    other = make_call_record(session, call_id="CALL-002")
    repo.create(
        call_record_id=other.id,
        text_full="Курьер согласовывает время доставки аксессуаров.",
    )

    results = repo.search("возврат", limit=5)
    assert len(results) == 1
    match = results[0]
    assert match.transcript.call_record_id == record.id
    assert "<mark>возврат</mark>" in match.snippet.lower()
    assert match.snippet.startswith("Менеджер")


def test_search_honors_limit_and_offset(session: Session) -> None:
    repo = B24TranscriptRepository(session)
    first = make_call_record(session, call_id="CALL-010")
    repo.create(
        call_record_id=first.id,
        text_full="Клиент уточняет статус возврата и запрашивает курьера.",
    )
    second = make_call_record(session, call_id="CALL-011")
    repo.create(
        call_record_id=second.id,
        text_full="Супервайзер передаёт клиенту информацию и подтверждает возврат.",
    )
    third = make_call_record(session, call_id="CALL-012")
    repo.create(
        call_record_id=third.id,
        text_full="Менеджер приветствует клиента и обсуждает ремонт устройства.",
    )

    page_one = repo.search("клиент", limit=1)
    assert len(page_one) == 1
    assert page_one[0].transcript.call_record_id == first.id

    page_two = repo.search("клиент", limit=1, offset=1)
    assert len(page_two) == 1
    assert page_two[0].transcript.call_record_id == second.id


def test_search_returns_empty_for_blank_query(session: Session) -> None:
    repo = B24TranscriptRepository(session)
    assert repo.search("   ") == []
    assert repo.search("", limit=5) == []
    assert repo.search("клиент", limit=0) == []
