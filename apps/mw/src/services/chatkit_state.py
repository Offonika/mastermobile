"""State helpers for ChatKit widget interactions."""
from __future__ import annotations

from apps.mw.src.services.state import KeyValueStore, build_store

AWAITING_QUERY_TTL_SECONDS = 300
_STORE: KeyValueStore = build_store("chatkit:awaiting")


def mark_awaiting_query(thread_id: str) -> None:
    """Remember that the thread awaits the next user query."""

    if not thread_id:
        return
    _STORE.set(thread_id, True, ttl=AWAITING_QUERY_TTL_SECONDS)


def is_awaiting_query(thread_id: str) -> bool:
    """Check whether a thread is waiting for the next user query."""

    if not thread_id:
        return False
    value = _STORE.get(thread_id, False)
    return bool(value)


def pop_awaiting_query(thread_id: str) -> bool:
    """Remove and return the awaiting query flag if present."""

    if not thread_id:
        return False
    value = _STORE.pop(thread_id, False)
    return bool(value)


def reset_awaiting_query_state() -> None:
    """Clear all recorded awaiting query flags (primarily for tests)."""

    _STORE.clear()

