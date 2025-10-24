"""Unit tests for the ChatKit service helpers."""

from __future__ import annotations

import httpx
import pytest

from apps.mw.src.services.chatkit import create_chatkit_session


class _DummyClient:
    """Minimal httpx.Client stand-in capturing POST invocations."""

    def __init__(self, attempts: list[tuple[str, dict[str, str], dict[str, object]]]):
        self._attempts = attempts

    def __enter__(self) -> _DummyClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - no cleanup required
        return None

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> httpx.Response:
        self._attempts.append((url, headers, json))
        if url.endswith("/realtime/sessions"):
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"client_secret": {"value": "secret-123"}},
            )

        return httpx.Response(
            404,
            request=httpx.Request("POST", url),
            text="not found",
        )


@pytest.mark.parametrize(
    "env_workflow, env_model",
    [
        ("wf_legacy_id", "gpt-4o-realtime-preview"),
    ],
)
def test_create_chatkit_session_prefers_realtime_endpoint(monkeypatch, env_workflow: str, env_model: str) -> None:
    """Realtime endpoint should be attempted first and succeed when available."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_WORKFLOW_ID", env_workflow)
    monkeypatch.setenv("OPENAI_CHATKIT_MODEL", env_model)

    attempts: list[tuple[str, dict[str, str], dict[str, object]]] = []

    monkeypatch.setattr(
        "apps.mw.src.services.chatkit.httpx.Client",
        lambda *args, **kwargs: _DummyClient(attempts),
    )

    secret = create_chatkit_session(env_workflow)

    assert secret == "secret-123"
    assert attempts, "Expected at least one HTTP call"

    first_url, first_headers, first_payload = attempts[0]
    assert first_url.endswith("/realtime/sessions")
    assert first_headers.get("OpenAI-Beta") == "realtime=v1"
    assert first_payload.get("model") == env_model
    assert "workflow_id" not in first_payload
