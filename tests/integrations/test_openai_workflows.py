from __future__ import annotations

import json
from typing import Any

import pytest
from openai import OpenAIError

from apps.mw.src.config.settings import Settings
from apps.mw.src.integrations.openai import workflows
from apps.mw.src.integrations.openai.workflows import (
    WorkflowInvocationError,
    forward_widget_action_to_workflow,
)


class _ResponsesStub:
    def __init__(self, calls: list[dict[str, Any]], *, should_fail: bool = False) -> None:
        self._calls = calls
        self._should_fail = should_fail

    async def create(self, **kwargs: Any) -> None:
        self._calls.append(kwargs)
        if self._should_fail:
            raise OpenAIError("simulated failure")


class _AsyncClientStub:
    def __init__(self, calls: list[dict[str, Any]], *, should_fail: bool = False) -> None:
        self.responses = _ResponsesStub(calls, should_fail=should_fail)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    workflows._CLIENT_CACHE.clear()
    yield
    workflows._CLIENT_CACHE.clear()


@pytest.mark.asyncio
async def test_forward_widget_action_to_workflow_builds_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        workflows,
        "_get_async_openai_client",
        lambda settings: _AsyncClientStub(calls),
    )

    settings = Settings(
        OPENAI_API_KEY="test-key",
        OPENAI_WORKFLOW_ID="workflow-123",
        OPENAI_BASE_URL="https://api.openai.com/v1",
    )

    await forward_widget_action_to_workflow(
        settings=settings,
        action={"type": "tool", "name": "search-docs", "payload": {"thread_id": "thread-1"}},
        request_id="req-1",
        tool_name="search-docs",
        thread_id="thread-1",
        conversation_identifier="thread-1",
        origin="https://example.com",
    )

    assert len(calls) == 1
    payload = json.loads(calls[0]["input"][0]["content"][0]["text"])
    assert payload["event"] == "chatkit.widget_action"
    assert payload["action"]["name"] == "search-docs"
    assert payload["context"]["thread_id"] == "thread-1"
    assert calls[0]["model"] == "workflow-123"
    assert calls[0]["metadata"]["request_id"] == "req-1"


@pytest.mark.asyncio
async def test_forward_widget_action_requires_workflow_id(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        workflows,
        "_get_async_openai_client",
        lambda settings: _AsyncClientStub(calls),
    )

    settings = Settings(OPENAI_API_KEY="test-key", OPENAI_WORKFLOW_ID="")

    with pytest.raises(WorkflowInvocationError):
        await forward_widget_action_to_workflow(
            settings=settings,
            action={"type": "tool", "name": "noop", "payload": {}},
            request_id="req-2",
            tool_name="noop",
            thread_id=None,
            conversation_identifier=None,
            origin=None,
        )


@pytest.mark.asyncio
async def test_forward_widget_action_wraps_openai_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflows,
        "_get_async_openai_client",
        lambda settings: _AsyncClientStub([], should_fail=True),
    )

    settings = Settings(
        OPENAI_API_KEY="test-key",
        OPENAI_WORKFLOW_ID="workflow-456",
    )

    with pytest.raises(WorkflowInvocationError):
        await forward_widget_action_to_workflow(
            settings=settings,
            action={"type": "tool", "name": "noop", "payload": {}},
            request_id="req-3",
            tool_name="noop",
            thread_id=None,
            conversation_identifier=None,
            origin=None,
        )
