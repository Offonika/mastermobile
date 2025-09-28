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


def test_create_transcript_persists_and_links(session: Session) -> None:
    record = make_call_record(session)
    repo = B24TranscriptRepository(session)

    transcript = repo.create(
        call_record_id=record.id,
        text_full="Менеджер общается с клиентом о возврате устройства.",
        text_normalized="менеджер общается с клиентом о возврате устройства",
        metadata={"segments": []},
    )

    session.refresh(record)
    assert transcript.id is not None
    assert record.transcript is transcript
    assert transcript.metadata_json == {"segments": []}


def test_get_by_call_record_id_returns_none_when_absent(session: Session) -> None:
    repo = B24TranscriptRepository(session)
    assert repo.get_by_call_record_id(9999) is None


def test_get_by_call_record_id_returns_existing_transcript(session: Session) -> None:
    record = make_call_record(session)
    repo = B24TranscriptRepository(session)
    repo.create(call_record_id=record.id, text_full="Добрый день", metadata=None)

    found = repo.get_by_call_record_id(record.id)
    assert found is not None
    assert found.call_record_id == record.id


def test_update_transcript_changes_fields(session: Session) -> None:
    record = make_call_record(session)
    repo = B24TranscriptRepository(session)
    transcript = repo.create(
        call_record_id=record.id,
        text_full="Начальная версия",
        text_normalized="начальная версия",
        metadata={"segments": ["intro"]},
    )

    updated = repo.update(
        transcript,
        text_full="Обновлённая версия стенограммы",
        text_normalized="обновленная версия стенограммы",
        metadata={"segments": ["intro", "resolution"]},
    )

    assert updated.text_full.startswith("Обновлённая")
    assert updated.text_normalized.endswith("стенограммы")
    assert updated.metadata_json == {"segments": ["intro", "resolution"]}


def test_delete_transcript_removes_relationship(session: Session) -> None:
    record = make_call_record(session)
    repo = B24TranscriptRepository(session)
    transcript = repo.create(call_record_id=record.id, text_full="Удаляемая стенограмма")

    repo.delete(transcript)
    session.expire(record, ["transcript"])

    assert record.transcript is None
    assert repo.get_by_call_record_id(record.id) is None
