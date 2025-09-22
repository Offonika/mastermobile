"""Tests for database session factory configuration."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from apps.mw.src.app import app
from apps.mw.src.db import Base
from apps.mw.src.db.session import configure_engine, get_session
from apps.mw.src.db.session import engine as default_engine


def test_get_session_provides_in_memory_sqlite_session() -> None:
    """`get_session` should yield a working SQLite session for tests."""

    sqlite_engine: Engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(sqlite_engine)

    session_gen: Generator[Session, None, None] | None = None
    override_gen: Generator[Session, None, None] | None = None

    try:
        configure_engine(sqlite_engine)

        session_gen = get_session()
        session = next(session_gen)

        result = session.execute(text("SELECT 1")).scalar_one()
        assert result == 1
        assert str(session.get_bind().url).startswith("sqlite+pysqlite://")

        def override_get_session() -> Generator[Session, None, None]:
            override_session = Session(bind=sqlite_engine)
            try:
                yield override_session
            finally:
                override_session.close()

        app.dependency_overrides[get_session] = override_get_session

        override_gen = app.dependency_overrides[get_session]()
        override_session = next(override_gen)
        override_result = override_session.execute(text("SELECT 1")).scalar_one()
        assert override_result == 1
        assert str(override_session.get_bind().url).startswith("sqlite+pysqlite://")
    finally:
        if session_gen is not None:
            session_gen.close()
        if override_gen is not None:
            override_gen.close()
        app.dependency_overrides.pop(get_session, None)
        configure_engine(default_engine)
        sqlite_engine.dispose()
