"""Minimal subset of the httpx API used by smoke tests.

This fallback client issues synchronous HTTP requests in a background thread
via the standard library. It is intentionally tiny and should be replaced with
the official dependency when available in the environment.
"""

from __future__ import annotations

import asyncio
import http.client
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

__all__ = [
    "ASGITransport",
    "AsyncBaseTransport",
    "AsyncClient",
    "BaseTransport",
    "Client",
    "Limits",
    "Proxy",
    "Response",
    "Timeout",
    "URL",
]


class URL(str):
    """Lightweight replacement for :class:`httpx.URL`."""


class Proxy:
    """Placeholder proxy configuration used by the OpenAI SDK."""

    def __init__(self, url: str, **_: Any) -> None:
        self.url = url


class Timeout:
    """Simplified timeout container matching the signature used by OpenAI."""

    def __init__(self, timeout: float | None = None, **kwargs: Any) -> None:
        self.timeout = timeout
        for key, value in kwargs.items():
            setattr(self, key, value)


class Limits:
    """Placeholder connection limits container."""

    def __init__(
        self,
        max_connections: int | None = None,
        max_keepalive_connections: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        for key, value in kwargs.items():
            setattr(self, key, value)


class BaseTransport:
    """Base transport placeholder to satisfy third-party imports."""


class AsyncBaseTransport(BaseTransport):
    """Async transport placeholder used for compatibility only."""


class ASGITransport(AsyncBaseTransport):
    """Stub ASGI transport; real implementation provided by optional dependency."""

    def __init__(self, app: Any) -> None:  # pragma: no cover - optional behaviour
        self.app = app


@dataclass
class Response:
    status_code: int
    _body: bytes

    def json(self) -> dict[str, Any]:
        return json.loads(self._body.decode("utf-8"))


class AsyncClient:
    def __init__(self, base_url: str, timeout: float | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, path: str) -> Response:
        url = self._build_url(path)
        return await asyncio.to_thread(self._request, "GET", url)

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{self._base_url}{path}"

    def _request(self, method: str, url: str) -> Response:
        parts = urlsplit(url)
        if parts.scheme != "http":
            msg = "Only http scheme is supported by the lightweight client"
            raise ValueError(msg)
        connection = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=self._timeout)
        target = parts.path or "/"
        if parts.query:
            target = f"{target}?{parts.query}"
        connection.request(method, target)
        response = connection.getresponse()
        body = response.read()
        connection.close()
        return Response(status_code=response.status, _body=body)


class Client:
    """Synchronous counterpart used to satisfy imports from optional deps."""

    def __init__(self, base_url: str, timeout: float | None = None) -> None:
        self._async = AsyncClient(base_url=base_url, timeout=timeout)

    def get(self, path: str) -> Response:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._async.get(path))
        finally:
            asyncio.set_event_loop(None)
            loop.close()
