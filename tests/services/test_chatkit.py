"""Unit tests for the ChatKit service helpers."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx
import pytest

from apps.mw.src.services.chatkit import (
    create_chatkit_service_session,
    create_chatkit_session,
)


class _ClientStub:
    """Context manager emulating :class:`httpx.Client`."""

    def __init__(self, responses: Sequence[httpx.Response]):
        self._responses = list(responses)
        self.requests: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def __enter__(self) -> _ClientStub:  # pragma: no cover - trivial
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - no cleanup
        return None

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> httpx.Response:
        """Record the request and return the next configured response."""

        self.requests.append((url, headers, json))
        if not self._responses:
            raise RuntimeError("No response configured for httpx.Client stub")
        return self._responses.pop(0)


def _patch_httpx_client(
    monkeypatch: pytest.MonkeyPatch,
    responses: Sequence[httpx.Response],
) -> list[_ClientStub]:
    """Patch ``httpx.Client`` to use the stub and return created instances."""

    instances: list[_ClientStub] = []

    def _factory(*args: Any, **kwargs: Any) -> _ClientStub:
        client = _ClientStub(responses)
        instances.append(client)
        return client

    monkeypatch.setattr("apps.mw.src.services.chatkit.httpx.Client", _factory)
    return instances


def _make_response(status_code: int, *, json: dict[str, Any] | None = None, text: str = "") -> httpx.Response:
    """Utility for building httpx responses with attached requests."""

    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions/sessions")
    if json is None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json, request=request)


def test_create_chatkit_service_session_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful API call should yield the client secret value."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("OPENAI_CHATKIT_MODEL", "gpt-4o-mini")

    responses = [_make_response(200, json={"client_secret": {"value": "secret-123"}})]
    instances = _patch_httpx_client(monkeypatch, responses)

    secret = create_chatkit_service_session()

    assert secret == "secret-123"
    assert instances, "Expected httpx.Client to be instantiated"

    url, headers, payload = instances[0].requests[0]
    assert url == "https://api.openai.com/v1/chat/completions/sessions"
    assert headers == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
        "OpenAI-Beta": "chat-completions",
    }
    assert payload == {"model": "gpt-4o-mini"}


def test_create_chatkit_service_session_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The service should raise if the API key is absent."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        create_chatkit_service_session()


def test_create_chatkit_service_session_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the response lacks the client secret we should raise an error."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    responses = [_make_response(200, json={"client_secret": {}})]
    _patch_httpx_client(monkeypatch, responses)

    with pytest.raises(RuntimeError, match="client_secret"):
        create_chatkit_service_session()


def test_create_chatkit_service_session_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP failures should propagate ``HTTPStatusError`` to the caller."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    error_response = _make_response(502, json={"error": "bad gateway"})
    responses = [error_response]
    instances = _patch_httpx_client(monkeypatch, responses)

    with pytest.raises(httpx.HTTPStatusError):
        create_chatkit_service_session()

    assert instances, "Expected httpx.Client to capture the failed request"
    assert instances[0].requests[0][0] == "https://api.openai.com/v1/chat/completions/sessions"


def test_create_chatkit_session_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """The legacy alias should simply delegate to the service helper."""

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    responses = [_make_response(200, json={"client_secret": {"value": "secret-456"}})]
    _patch_httpx_client(monkeypatch, responses)

    assert create_chatkit_session() == "secret-456"

