"""Unit tests for the ChatKit service helpers."""

from __future__ import annotations

import httpx
import pytest

from apps.mw.src.services.chatkit import create_chatkit_service_session


class _DummyClient:
    """Minimal httpx.Client stand-in capturing POST invocations."""

    def __init__(self, attempts: list[tuple[str, dict[str, str], dict[str, object]]]):
        self._attempts = attempts

    def __enter__(self) -> "_DummyClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - no cleanup required
        return None

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> httpx.Response:
        self._attempts.append((url, headers, json))
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"client_secret": {"value": "secret-123"}},
        )


def test_create_chatkit_service_session_uses_chat_completions_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service should call the chat completions sessions endpoint with model only."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_CHATKIT_MODEL", raising=False)

    attempts: list[tuple[str, dict[str, str], dict[str, object]]] = []

    monkeypatch.setattr(
        "apps.mw.src.services.chatkit.httpx.Client",
        lambda *args, **kwargs: _DummyClient(attempts),
    )

    secret = create_chatkit_service_session()

    assert secret == "secret-123"
    assert attempts, "Expected at least one HTTP call"

    first_url, first_headers, first_payload = attempts[0]
    assert first_url == "https://api.openai.com/v1/chat/completions/sessions"
    assert first_headers == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
        "OpenAI-Beta": "chat-completions",
    }
    assert first_payload == {"model": "gpt-4o-mini"}
