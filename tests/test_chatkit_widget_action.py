from __future__ import annotations

from typing import Any

import pytest

from apps.mw.src.api.routers.chatkit import WidgetActionRequest, handle_widget_action
from apps.mw.src.config.settings import get_settings
from apps.mw.src.services.chatkit_state import (
    is_awaiting_query,
    reset_awaiting_query_state,
)


@pytest.fixture(autouse=True)
def _patch_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(**_: Any) -> str | None:
        return "   "

    monkeypatch.setattr(
        "apps.mw.src.api.routers.chatkit.forward_widget_action_to_workflow",
        _noop,
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_WORKFLOW_ID", "workflow-id")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_chatkit_state() -> None:
    reset_awaiting_query_state()
    yield
    reset_awaiting_query_state()


@pytest.mark.asyncio
async def test_search_docs_action_prefers_thread_header() -> None:
    action = WidgetActionRequest(
        type="tool",
        name="search-docs",
        payload={"thread_id": "payload-thread"},
    )

    response = await handle_widget_action(
        action,
        request_id="req-123",
        thread_id="header-thread",
    )

    assert response.ok is True
    assert response.awaiting_query is True
    assert is_awaiting_query("header-thread")
    assert not is_awaiting_query("payload-thread")
    assert response.message is None


@pytest.mark.asyncio
async def test_other_tool_action_returns_simple_ack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _reply(**_: Any) -> str | None:
        return "  Ответ "

    monkeypatch.setattr(
        "apps.mw.src.api.routers.chatkit.forward_widget_action_to_workflow",
        _reply,
    )

    action = WidgetActionRequest(
        type="tool",
        name="handbook",
        payload={"thread_id": "thread-xyz"},
    )

    response = await handle_widget_action(action, request_id="req-456")

    assert response.ok is True
    assert response.awaiting_query is None
    assert not is_awaiting_query("thread-xyz")
    assert response.message == "Ответ"


@pytest.mark.asyncio
async def test_legacy_tool_name_format_is_supported() -> None:
    action = WidgetActionRequest(
        type="tool.search-docs",
        payload={"session_id": "session-789"},
    )

    response = await handle_widget_action(action, request_id="req-789")

    assert response.ok is True
    assert response.awaiting_query is True
    assert is_awaiting_query("session-789")
    assert response.message is None


@pytest.mark.asyncio
async def test_search_docs_action_falls_back_to_payload_identifier() -> None:
    action = WidgetActionRequest(
        type="tool",
        name="search-docs",
        payload={"thread_id": "payload-thread"},
    )

    response = await handle_widget_action(action, request_id="req-234")

    assert response.ok is True
    assert response.awaiting_query is True
    assert is_awaiting_query("payload-thread")
    assert response.message is None
