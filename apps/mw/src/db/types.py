"""Database type helpers for MasterMobile middleware."""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON, TypeDecorator


class JSONBType(TypeDecorator[Any]):
    """JSONB-compatible type that falls back to JSON on SQLite."""

    impl = JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "sqlite":
            return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(JSONB())

