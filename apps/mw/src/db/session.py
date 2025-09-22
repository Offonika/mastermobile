"""Database session management utilities."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from apps.mw.src.config import get_settings

_settings = get_settings()

engine: Engine = create_engine(
    _settings.sqlalchemy_database_uri,
    future=True,
    pool_pre_ping=True,
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def configure_engine(bind: Engine) -> None:
    """Rebind the session factory to a different engine (used for tests)."""

    global engine
    engine = bind
    SessionLocal.configure(bind=bind)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
