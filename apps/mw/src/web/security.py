"""Security helpers for the static assistant frontend."""

from __future__ import annotations

from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

ASSISTANT_PATH_PREFIX: Final[str] = "/assistant"
DEFAULT_ASSISTANT_CSP: Final[str] = (
    "default-src 'none'; "
    "base-uri 'self'; "
    "connect-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "img-src 'self' data:; "
    "manifest-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;"
)
CACHE_CONTROL_NO_CACHE: Final[str] = "no-cache"


class AssistantSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject CSP and cache-control headers for assistant assets."""

    def __init__(
        self,
        app,
        *,
        csp: str = DEFAULT_ASSISTANT_CSP,
        cache_control: str = CACHE_CONTROL_NO_CACHE,
        path_prefix: str = ASSISTANT_PATH_PREFIX,
    ) -> None:
        super().__init__(app)
        self._csp = csp
        self._cache_control = cache_control
        self._path_prefix = path_prefix.rstrip("/") or "/"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        path = request.url.path
        if self._matches_prefix(path):
            response.headers.setdefault("Content-Security-Policy", self._csp)
            response.headers["Cache-Control"] = self._cache_control
        return response

    def _matches_prefix(self, path: str) -> bool:
        prefix = self._path_prefix
        if prefix == "/":
            return True
        return path == prefix or path.startswith(f"{prefix}/")
