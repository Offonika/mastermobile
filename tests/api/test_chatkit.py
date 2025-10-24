"""API tests covering ChatKit integration endpoints."""

from __future__ import annotations

import httpx
import pytest

from apps.mw.src.app import app
from apps.mw.src.config.settings import get_settings

BASE_URL = "http://testserver"


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    """Ensure settings are reloaded for each test case."""

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_session_returns_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session endpoint should proxy the secret from the ChatKit service."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "apps.mw.src.api.routers.chatkit.create_chatkit_service_session",
        lambda: "client-secret-abc",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post("/api/v1/chatkit/session")

    assert response.status_code == 200
    assert response.json() == {"client_secret": "client-secret-abc"}


@pytest.mark.asyncio
async def test_widget_action_new_format_search_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    """New format tools should mark awaiting search queries using the thread id."""

    captured: dict[str, str] = {}

    def _mark(identifier: str) -> None:
        captured["identifier"] = identifier

    monkeypatch.setattr("apps.mw.src.api.routers.chatkit.mark_awaiting_query", _mark)

    payload = {
        "type": "tool",
        "name": "search-docs",
        "payload": {"conversation_id": "conv-123"},
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/v1/chatkit/widget-action",
            json=payload,
            headers={"x-chatkit-thread-id": "thread-abc"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "awaiting_query": True}
    assert captured.get("identifier") == "thread-abc"


@pytest.mark.asyncio
async def test_widget_action_legacy_format_search_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy tool type should still be accepted and mark awaiting queries."""

    captured: dict[str, str] = {}

    def _mark(identifier: str) -> None:
        captured["identifier"] = identifier

    monkeypatch.setattr("apps.mw.src.api.routers.chatkit.mark_awaiting_query", _mark)

    payload = {
        "type": "tool.search-docs",
        "payload": {"session_id": "session-xyz"},
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/v1/chatkit/widget-action",
            json=payload,
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "awaiting_query": True}
    assert captured.get("identifier") == "session-xyz"


@pytest.mark.asyncio
async def test_widget_action_unknown_tool_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unsupported tool actions should return a negative acknowledgement."""

    called = False

    def _mark(_: str) -> None:  # pragma: no cover - defensive guard
        nonlocal called
        called = True

    monkeypatch.setattr("apps.mw.src.api.routers.chatkit.mark_awaiting_query", _mark)

    payload = {
        "type": "tool",
        "payload": {},
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/v1/chatkit/widget-action",
            json=payload,
        )

    assert response.status_code == 200
    assert response.json() == {"ok": False, "awaiting_query": None}
    assert not called
