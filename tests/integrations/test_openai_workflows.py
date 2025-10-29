from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pytest_httpx import HTTPXMock

from apps.mw.src.config.settings import Settings
from apps.mw.src.integrations.openai import workflows
from apps.mw.src.integrations.openai.workflows import (
    WorkflowInvocationError,
    forward_widget_action_to_workflow,
)
from apps.mw.src.observability.metrics import WORKFLOWS_ERRORS_TOTAL


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    workflows._CLIENT_CACHE.clear()
    yield
    workflows._CLIENT_CACHE.clear()


@pytest.mark.asyncio
async def test_forward_widget_action_to_workflow_builds_payload(
    httpx_mock: HTTPXMock,
) -> None:
    recorded: dict[str, Any] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        recorded["headers"] = dict(request.headers)
        recorded["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={
                "id": "wr_123",
                "status": "completed",
                "outputs": [
                    {
                        "content": [
                            {"type": "output_text", "text": "Workflow reply"},
                        ]
                    }
                ],
            },
        )

    httpx_mock.add_callback(
        _handler,
        method="POST",
        url="https://example.com/v1/workflows/runs",
    )

    settings = Settings(
        OPENAI_API_KEY="test-key",
        OPENAI_PROJECT="project-1",
        OPENAI_BASE_URL="https://example.com/v1",
        OPENAI_WORKFLOW_ID="workflow-123",
    )

    result = await forward_widget_action_to_workflow(
        settings=settings,
        action={"type": "tool", "name": "search-docs", "payload": {"thread_id": "thread-1"}},
        request_id="req-1",
        tool_name="search-docs",
        thread_id="thread-1",
        conversation_identifier="thread-1",
        origin="https://example.com",
    )

    assert recorded["json"]["workflow_id"] == "workflow-123"
    assert recorded["json"]["inputs"]["payload"]["action"]["name"] == "search-docs"
    assert recorded["json"]["inputs"]["metadata"]["request_id"] == "req-1"
    assert recorded["headers"].get("openai-beta") == "workflows=v1"
    assert result == "Workflow reply"


@pytest.mark.asyncio
async def test_forward_widget_action_requires_workflow_id() -> None:
    settings = Settings(
        OPENAI_API_KEY="test-key",
        OPENAI_PROJECT="project-1",
        OPENAI_BASE_URL="https://example.com/v1",
        OPENAI_WORKFLOW_ID="",
    )

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
async def test_forward_widget_action_records_metrics_for_status_error(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://example.com/v1/workflows/runs",
        status_code=400,
        json={"error": {"message": "bad request"}},
    )

    settings = Settings(
        OPENAI_API_KEY="test-key",
        OPENAI_PROJECT="project-1",
        OPENAI_BASE_URL="https://example.com/v1",
        OPENAI_WORKFLOW_ID="workflow-456",
    )

    counter = WORKFLOWS_ERRORS_TOTAL.labels(reason="status_400")
    before = counter._value.get()

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

    assert counter._value.get() == before + 1


@pytest.mark.asyncio
async def test_forward_widget_action_wraps_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Client:
        async def post(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # pragma: no cover - stub
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(
        workflows,
        "_get_async_openai_client",
        lambda settings: _Client(),
    )

    settings = Settings(
        OPENAI_API_KEY="test-key",
        OPENAI_PROJECT="project-1",
        OPENAI_BASE_URL="https://example.com/v1",
        OPENAI_WORKFLOW_ID="workflow-789",
    )

    with pytest.raises(WorkflowInvocationError):
        await forward_widget_action_to_workflow(
            settings=settings,
            action={"type": "tool", "name": "noop", "payload": {}},
            request_id="req-4",
            tool_name="noop",
            thread_id=None,
            conversation_identifier=None,
            origin=None,
        )
