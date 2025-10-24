"""Unit tests for the ChatKit service helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from apps.mw.src.services.chatkit import create_chatkit_service_session


class _DummyClient:
    """Context manager that captures ``post`` invocations."""

    def __init__(self, responder: Callable[[str, dict[str, str], dict[str, Any]], httpx.Response]):
        self._responder = responder
        self.calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def __enter__(self) -> "_DummyClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - nothing to clean up
        return None

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> httpx.Response:
        self.calls.append((url, headers, json))
        return self._responder(url, headers, json)


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ChatKit specific environment variables are reset for each test."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_CHATKIT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_CHATKIT_VOICE", raising=False)


def _patch_httpx_client(
    monkeypatch: pytest.MonkeyPatch,
    responder: Callable[[str, dict[str, str], dict[str, Any]], httpx.Response],
) -> _DummyClient:
    """Replace :class:`httpx.Client` with a deterministic double."""

    client = _DummyClient(responder)

    class _ClientFactory:
        def __call__(self, *args: Any, **kwargs: Any) -> _DummyClient:  # pragma: no cover - thin wrapper
            return client

    monkeypatch.setattr(httpx, "Client", _ClientFactory())
    return client


def test_create_chatkit_service_session_calls_realtime_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service helper should call the realtime sessions endpoint with default payload."""

    def _responder(url: str, headers: dict[str, str], payload: dict[str, Any]) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            request=httpx.Request("POST", url),
            json={"client_secret": {"value": "secret-123"}},
        )

    client = _patch_httpx_client(monkeypatch, _responder)

    secret = create_chatkit_service_session()

    assert secret == "secret-123"
    assert client.calls, "Expected HTTP request to be issued"
    url, headers, payload = client.calls[0]
    assert url == "https://api.openai.com/v1/realtime/sessions"
    assert headers == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
        "OpenAI-Beta": "realtime=v1",
    }
    assert payload == {"model": "gpt-4o-mini"}


def test_create_chatkit_service_session_includes_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configured base URL, model and voice should be used in the request payload."""

    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1/")
    monkeypatch.setenv("OPENAI_CHATKIT_MODEL", "gpt-4o-realtime-preview")
    monkeypatch.setenv("OPENAI_CHATKIT_VOICE", "alloy")

    def _responder(url: str, headers: dict[str, str], payload: dict[str, Any]) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            request=httpx.Request("POST", url),
            json={"client_secret": {"value": "secret-456"}},
        )

    client = _patch_httpx_client(monkeypatch, _responder)

    secret = create_chatkit_service_session()

    assert secret == "secret-456"
    url, _, payload = client.calls[0]
    assert url == "https://api.openai.com/v1/realtime/sessions"
    assert payload == {"model": "gpt-4o-realtime-preview", "voice": "alloy"}


def test_create_chatkit_service_session_raises_for_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP errors from OpenAI should be propagated for the router to handle."""

    def _responder(url: str, headers: dict[str, str], payload: dict[str, Any]) -> httpx.Response:
        response = httpx.Response(
            status_code=502,
            request=httpx.Request("POST", url),
            text="bad gateway",
        )
        # ``create_chatkit_service_session`` expects the response object to provide
        # ``status_code`` and ``text`` so we raise the same exception httpx would.
        response.raise_for_status()

    client = _patch_httpx_client(monkeypatch, _responder)

    with pytest.raises(httpx.HTTPError):
        create_chatkit_service_session()

    assert client.calls, "Expected failing request to be attempted"


def test_create_chatkit_service_session_raises_when_secret_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the response lacks a client secret the helper should raise a runtime error."""

    def _responder(url: str, headers: dict[str, str], payload: dict[str, Any]) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            request=httpx.Request("POST", url),
            json={},
        )

    _patch_httpx_client(monkeypatch, _responder)

    with pytest.raises(RuntimeError, match="No client_secret"):
        create_chatkit_service_session()
