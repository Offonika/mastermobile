"""In-memory state helpers for ChatKit widget interactions."""
from __future__ import annotations

import threading

_FILE_SEARCH_INTENTS: dict[str, bool] = {}
_LOCK = threading.Lock()


def mark_file_search_intent(conversation_id: str) -> None:
    """Remember that the conversation awaits a file search query."""

    if not conversation_id:
        return
    with _LOCK:
        _FILE_SEARCH_INTENTS[conversation_id] = True


def is_file_search_intent_pending(conversation_id: str) -> bool:
    """Check whether a conversation is waiting for a file search query."""

    with _LOCK:
        return _FILE_SEARCH_INTENTS.get(conversation_id, False)


def pop_file_search_intent(conversation_id: str) -> bool:
    """Remove and return the pending search intent flag if present."""

    with _LOCK:
        return bool(_FILE_SEARCH_INTENTS.pop(conversation_id, None))


def reset_file_search_intents() -> None:
    """Clear all recorded file search intents (primarily for tests)."""

    with _LOCK:
        _FILE_SEARCH_INTENTS.clear()

