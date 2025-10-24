"""Unit tests for the ChatKit service helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from openai import OpenAIError

from apps.mw.src.services.chatkit import create_chatkit_service_session


@dataclass
class _DummyClientSecretResponse:
    """Minimal stand-in for the OpenAI client secret response."""

    value: str


class _DummyClientSecrets:
    """Capture invocations of ``client.realtime.client_secrets.create``."""

    def __init__(self, responses: list[Any]):
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def create(self, *, session: dict[str, Any], extra_headers: dict[str, str] | None = None):
        self.calls.append({"session": session, "extra_headers": extra_headers})
        if not self._responses:
            raise RuntimeError("No responses configured for dummy client secrets")
        outcome = self._responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _DummyRealtime:
    """Container for the ``client_secrets`` helper."""

    def __init__(self, client_secrets: _DummyClientSecrets):
        self.client_secrets = client_secrets


class _DummyOpenAI:
    """Minimal stand-in for the ``OpenAI`` SDK client."""

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


    def __init__(self, responses: list[Any], kwargs: dict[str, Any]):
        self.kwargs = kwargs
        self.closed = False
        self._client_secrets = _DummyClientSecrets(responses)
        self.realtime = _DummyRealtime(self._client_secrets)

    def close(self) -> None:
        self.closed = True


class _OpenAIFactory:
    def __init__(self, responses: list[Any]):
        self._responses = responses
        self.instances: list[_DummyOpenAI] = []

    def __call__(self, **kwargs: Any) -> _DummyOpenAI:
        instance = _DummyOpenAI(self._responses, kwargs)
        self.instances.append(instance)
        return instance


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure environment variables required by settings are set per test."""

    monkeypatch.delenv("OPENAI_CHATKIT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_CHATKIT_VOICE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_CHATKIT_MODEL", raising=False)


def test_create_chatkit_session_uses_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a model override is present it should be used for the session payload."""

    monkeypatch.setenv("OPENAI_CHATKIT_MODEL", "gpt-4o-realtime-preview")


    secret = create_chatkit_service_session()


    assert secret == "secret-123"
    assert factory.instances, "Expected OpenAI client to be instantiated"

    instance = factory.instances[0]
    assert instance.closed, "OpenAI client should be closed after use"
    assert instance.kwargs["api_key"] == "test-key"
    assert instance.kwargs["base_url"].endswith("/v1")

    calls = instance.realtime.client_secrets.calls
    assert calls, "Expected at least one client secret creation attempt"
    first_call = calls[0]
    assert first_call["session"] == {"type": "realtime", "model": "gpt-4o-realtime-preview"}
    assert first_call["extra_headers"] == {"OpenAI-Beta": "realtime=v1"}


def test_create_chatkit_session_falls_back_to_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """If no override exists, the workflow identifier should be used as the model."""

    monkeypatch.delenv("OPENAI_CHATKIT_MODEL", raising=False)

    responses = [_DummyClientSecretResponse("secret-456")]
    factory = _patch_openai(monkeypatch, responses)

    secret = create_chatkit_session("gpt-4o-realtime-preview-2024-12-17")

    assert secret == "secret-456"
    call = factory.instances[0].realtime.client_secrets.calls[0]
    assert call["session"] == {
        "type": "realtime",
        "model": "gpt-4o-realtime-preview-2024-12-17",
    }


def test_create_chatkit_session_includes_voice_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Voice overrides should be mapped to the realtime audio output settings."""

    monkeypatch.setenv("OPENAI_CHATKIT_MODEL", "gpt-4o-mini-realtime-preview")
    monkeypatch.setenv("OPENAI_CHATKIT_VOICE", "verse")

    responses = [_DummyClientSecretResponse("secret-789")]
    factory = _patch_openai(monkeypatch, responses)

    secret = create_chatkit_session("wf_ignored")

    assert secret == "secret-789"
    call = factory.instances[0].realtime.client_secrets.calls[0]
    assert call["session"] == {
        "type": "realtime",
        "model": "gpt-4o-mini-realtime-preview",
        "audio": {"output": {"voice": "verse"}},
    }


def test_create_chatkit_session_raises_when_openai_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenAI errors should be surfaced after exhausting retries."""

    responses = [OpenAIError("bad request"), OpenAIError("bad request")]
    factory = _patch_openai(monkeypatch, responses)

    with pytest.raises(OpenAIError):
        create_chatkit_session("wf_failure")

    first_url, first_headers, first_payload = attempts[0]
    assert first_url == "https://api.openai.com/v1/chat/completions/sessions"
    assert first_headers == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
        "OpenAI-Beta": "chat-completions",
    }
    assert first_payload == {"model": "gpt-4o-mini"}

