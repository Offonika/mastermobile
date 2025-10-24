"""API tests covering ChatKit integration endpoints."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from apps.mw.src.api.routers import chatkit as chatkit_router
from apps.mw.src.api.routes import chatkit as chatkit_routes
from apps.mw.src.config.settings import get_settings


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
    monkeypatch.setattr(
        "apps.mw.src.api.routers.chatkit.create_chatkit_service_session",
        lambda: "client-secret-abc",
    )

    response = await chatkit_router.create_chatkit_session(request_id="req-chatkit-session")


    assert response.client_secret == "client-secret-abc"


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

    upload_file = UploadFile(
        file=BytesIO(b"%PDF-1.4"),
        filename="handbook.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    response = await chatkit_routes.upload_to_vector_store(
        file=upload_file,
        title="Handbook",
        dept="Support",
        version="1.0",
        updated_at="2024-01-01",
        source="manual",
        request_id="req-vector-upload",
    )

    assert response.status == "ok"
    assert response.filename == "handbook.pdf"
    assert response.metadata.title == "Handbook"

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
        "apps.mw.src.api.routers.chatkit.mark_awaiting_query",
        _mark,
    )

    payload = {
        "type": "tool.search-docs",
        "payload": {"session_id": "session-xyz"},
    }

    response = await chatkit_router.handle_widget_action(
        chatkit_router.WidgetActionRequest.model_validate(payload),
        request_id="req-widget-action",
    )

    assert response.model_dump() == {"ok": True, "awaiting_query": True}
    assert captured.get("identifier") == "session-xyz"


@pytest.mark.asyncio
async def test_widget_action_accepts_modern_tool_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """New-format tool actions with a separate name should be processed."""

    captured: dict[str, str] = {}

    def _mark(identifier: str) -> None:
        captured["identifier"] = identifier

    monkeypatch.setattr(
        "apps.mw.src.api.routers.chatkit.mark_awaiting_query",
        _mark,
    )

    payload = {
        "type": "tool",
        "name": "search-docs",
        "payload": {"conversation_id": "conv-123"},
    }

    response = await chatkit_router.handle_widget_action(
        chatkit_router.WidgetActionRequest.model_validate(payload),
        request_id="req-widget-action-modern",
        thread_id="header-thread",
    )

    assert response.model_dump() == {"ok": True, "awaiting_query": True}
    assert captured.get("identifier") == "header-thread"
