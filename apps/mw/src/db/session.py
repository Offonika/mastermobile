"""Database session factory used by the API layer."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_SQLITE_PATH = os.getenv("MASTER_MOBILE_SQLITE", "sqlite+pysqlite:///./mastermobile.db")

if DEFAULT_SQLITE_PATH.startswith("sqlite"):
    _CONNECT_ARGS = {"check_same_thread": False}
else:  # pragma: no cover - other drivers handled externally
    _CONNECT_ARGS = {}

engine = create_engine(DEFAULT_SQLITE_PATH, echo=False, future=True, connect_args=_CONNECT_ARGS)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def init_db() -> None:
    """Create database tables if they are missing."""

    Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session for FastAPI dependencies."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope for script usage."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["engine", "init_db", "get_session", "session_scope", "SessionLocal"]
