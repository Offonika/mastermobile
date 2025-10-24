"""In-memory state helpers for ChatKit widget interactions."""
from __future__ import annotations

import threading

_AWAITING_QUERY_FLAGS: dict[str, bool] = {}
_LOCK = threading.Lock()


def mark_awaiting_query(thread_id: str) -> None:
    """Remember that the thread awaits the next user query."""

    if not thread_id:
        return
    with _LOCK:
        _AWAITING_QUERY_FLAGS[thread_id] = True


def is_awaiting_query(thread_id: str) -> bool:
    """Check whether a thread is waiting for the next user query."""

    with _LOCK:
        return _AWAITING_QUERY_FLAGS.get(thread_id, False)


def pop_awaiting_query(thread_id: str) -> bool:
    """Remove and return the awaiting query flag if present."""

    with _LOCK:
        return bool(_AWAITING_QUERY_FLAGS.pop(thread_id, None))


def reset_awaiting_query_state() -> None:
    """Clear all recorded awaiting query flags (primarily for tests)."""

    with _LOCK:
        _AWAITING_QUERY_FLAGS.clear()

