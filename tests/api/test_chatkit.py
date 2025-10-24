"""API tests covering ChatKit integration endpoints."""

from __future__ import annotations

from types import SimpleNamespace

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
async def test_widget_session_returns_fixed_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """ChatKit widget session endpoint returns the client secret from the service."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_WORKFLOW_ID", "workflow-123")
    monkeypatch.setattr(
        "apps.mw.src.api.routers.chatkit.create_chatkit_session",
        lambda workflow_id: "client-secret-abc",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/v1/chatkit/session",
            headers={"X-Request-Id": "req-chatkit-session"},
        )

    assert response.status_code == 200
    assert response.json() == {"client_secret": "client-secret-abc"}


@pytest.mark.asyncio
async def test_vector_store_upload_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vector store upload should succeed with valid payload and document."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_VECTOR_STORE_ID", "vs_test_123")

    uploads: list[dict[str, object]] = []

    class _UploadRecorder:
        def upload(self, *, vector_store_id: str, file: dict[str, object], metadata: dict[str, object]) -> None:
            uploads.append(
                {
                    "vector_store_id": vector_store_id,
                    "file": file,
                    "metadata": metadata,
                }
            )

    fake_client = SimpleNamespace(vector_stores=SimpleNamespace(files=_UploadRecorder()))

    monkeypatch.setattr(
        "apps.mw.src.api.routes.chatkit._create_openai_client",
        lambda settings: fake_client,
    )

    files = {"file": ("handbook.pdf", b"%PDF-1.4", "application/pdf")}
    data = {
        "title": "Handbook",
        "dept": "Support",
        "version": "1.0",
        "updated_at": "2024-01-01",
        "source": "manual",
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/vector-store/upload",
            files=files,
            data=data,
            headers={"X-Request-Id": "req-vector-upload"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["filename"] == "handbook.pdf"
    assert body["metadata"]["title"] == "Handbook"

    assert uploads, "Expected OpenAI client upload to be invoked"
    recorded = uploads[0]
    assert recorded["vector_store_id"] == "vs_test_123"
    assert recorded["file"]["file_name"] == "handbook.pdf"
    assert recorded["metadata"]["title"] == "Handbook"


@pytest.mark.asyncio
async def test_widget_action_supports_legacy_tool_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy tool actions should still mark search intent and await a query."""

    captured: dict[str, str] = {}

    def _mark(identifier: str) -> None:
        captured["identifier"] = identifier

    monkeypatch.setattr(
        "apps.mw.src.api.routers.chatkit.mark_file_search_intent",
        _mark,
    )

    payload = {
        "type": "tool.search-docs",
        "payload": {"session_id": "session-xyz"},
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            "/api/v1/chatkit/widget-action",
            json=payload,
            headers={"X-Request-Id": "req-widget-action"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "awaiting_query": True}
    assert captured.get("identifier") == "session-xyz"


@pytest.mark.asyncio
async def test_widget_action_accepts_modern_tool_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """New-format tool actions with a separate name should be processed."""

    captured: dict[str, str] = {}

    def _mark(identifier: str) -> None:
        captured["identifier"] = identifier

    monkeypatch.setattr(
        "apps.mw.src.api.routers.chatkit.mark_file_search_intent",
        _mark,
    )

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
            headers={"X-Request-Id": "req-widget-action-modern"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "awaiting_query": True}
    assert captured.get("identifier") == "conv-123"
