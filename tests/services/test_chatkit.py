"""Unit tests for the ChatKit service helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from openai import OpenAIError

from apps.mw.src.services.chatkit import create_chatkit_session


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
    def __init__(self, client_secrets: _DummyClientSecrets):
        self.client_secrets = client_secrets



    def __enter__(self) -> _DummyClient:
        return self


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
    monkeypatch.setenv("OPENAI_WORKFLOW_ID", "wf_default")
    monkeypatch.delenv("OPENAI_BETA_HEADER", raising=False)
    monkeypatch.delenv("OPENAI_ORG", raising=False)
    monkeypatch.delenv("OPENAI_PROJECT", raising=False)


def _patch_openai(monkeypatch: pytest.MonkeyPatch, responses: list[Any]) -> _OpenAIFactory:
    factory = _OpenAIFactory(responses)
    monkeypatch.setattr("apps.mw.src.services.chatkit.OpenAI", factory)
    return factory


def test_create_chatkit_session_uses_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a model override is present it should be used for the session payload."""

    monkeypatch.setenv("OPENAI_CHATKIT_MODEL", "gpt-4o-realtime-preview")

    responses = [_DummyClientSecretResponse("secret-123")]
    factory = _patch_openai(monkeypatch, responses)

    secret = create_chatkit_session("wf_legacy")

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

    # Ensure at least one attempt was made before raising
    assert factory.instances[0].realtime.client_secrets.calls
