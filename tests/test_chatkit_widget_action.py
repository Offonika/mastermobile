from __future__ import annotations

import pytest

from apps.mw.src.api.routers.chatkit import WidgetActionRequest, handle_widget_action
from apps.mw.src.services.chatkit_state import (
    is_file_search_intent_pending,
    reset_file_search_intents,
)


@pytest.fixture(autouse=True)
def _reset_chatkit_state() -> None:
    reset_file_search_intents()
    yield
    reset_file_search_intents()


@pytest.mark.asyncio
async def test_search_docs_action_marks_pending_query() -> None:
    action = WidgetActionRequest(
        type="tool",
        name="search-docs",
        payload={"thread_id": "thread-123"},
    )

    response = await handle_widget_action(action, request_id="req-123")

    assert response.ok is True
    assert response.awaiting_query is True
    assert is_file_search_intent_pending("thread-123")


@pytest.mark.asyncio
async def test_other_tool_action_returns_simple_ack() -> None:
    action = WidgetActionRequest(
        type="tool",
        name="handbook",
        payload={"thread_id": "thread-xyz"},
    )

    response = await handle_widget_action(action, request_id="req-456")

    assert response.ok is True
    assert response.awaiting_query is None
    assert not is_file_search_intent_pending("thread-xyz")


@pytest.mark.asyncio
async def test_legacy_tool_name_format_is_supported() -> None:
    action = WidgetActionRequest(
        type="tool.search-docs",
        payload={"session_id": "session-789"},
    )

    response = await handle_widget_action(action, request_id="req-789")

    assert response.ok is True
    assert response.awaiting_query is True
    assert is_file_search_intent_pending("session-789")
