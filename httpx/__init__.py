"""Fallback subset of the httpx API for restricted environments."""

from __future__ import annotations

import asyncio
import http.client
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

__all__ = ["AsyncClient", "Response"]


@dataclass
class Response:
    status_code: int
    _body: bytes
    headers: dict[str, str]

    def json(self) -> Any:
        if not self._body:
            return None
        return json.loads(self._body.decode("utf-8"))


class AsyncClient:
    def __init__(self, base_url: str, timeout: float | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def __aenter__(self) -> AsyncClient:  # pragma: no cover - trivial
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - trivial
        return None

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        url = self._build_url(path)
        return await asyncio.to_thread(self._request, method, url, json_payload=json, headers=headers)

    async def get(self, path: str, *, headers: dict[str, str] | None = None) -> Response:
        return await self.request("GET", path, headers=headers)

    async def post(
        self,
        path: str,
        *,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        return await self.request("POST", path, json=json, headers=headers)

    async def put(
        self,
        path: str,
        *,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        return await self.request("PUT", path, json=json, headers=headers)

    async def delete(
        self,
        path: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> Response:
        return await self.request("DELETE", path, headers=headers)

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{self._base_url}{path}"

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_payload: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        parts = urlsplit(url)
        if parts.scheme != "http":
            msg = "Only http scheme is supported by the lightweight client"
            raise ValueError(msg)

        payload: bytes | None = None
        request_headers = headers.copy() if headers else {}
        if json_payload is not None:
            payload = json.dumps(json_payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        connection = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=self._timeout)
        target = parts.path or "/"
        if parts.query:
            target = f"{target}?{parts.query}"
        connection.request(method, target, body=payload, headers=request_headers)
        response = connection.getresponse()
        body = response.read()
        headers_dict = {key.title(): value for key, value in response.getheaders()}
        connection.close()
        return Response(status_code=response.status, _body=body, headers=headers_dict)
