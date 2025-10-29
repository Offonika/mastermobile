"""Service helpers for creating ChatKit sessions."""
from __future__ import annotations

from secrets import token_urlsafe
from typing import Any, cast

import httpx
from loguru import logger

from apps.mw.src.config import get_settings

__all__ = ["create_chatkit_service_session", "create_chatkit_session"]

_LOCAL_SECRET_PREFIX = "chatkit-local-secret-"


def _beta_headers(api_key: str) -> dict[str, str]:
    """Return headers required for the Realtime beta endpoints."""

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "realtime=v1",
    }


def _generate_local_secret() -> str:
    """Create a deterministic-looking secret for local development."""

    # token_urlsafe already includes randomness and base64 characters which
    # resemble the format returned by OpenAI. Prefix the value to make it clear
    # in logs that this secret is synthetic.
    return f"{_LOCAL_SECRET_PREFIX}{token_urlsafe(24)}"


def create_chatkit_service_session() -> str:
    """Create a ChatKit session using the Chat Completions Sessions API."""

    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip()

    if not api_key:
        logger.warning(
            "OPENAI_API_KEY is not set; returning a stub ChatKit secret for local use",
        )
        return _generate_local_secret()

    base_url = (settings.openai_base_url or "https://api.openai.com/v1").rstrip("/")
    sessions_url = f"{base_url}/realtime/sessions"
    headers = _beta_headers(api_key)

    with httpx.Client(timeout=20.0) as http:
        payload: dict[str, Any] = {}

        response = http.post(sessions_url, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            error_body = (response.text or "")[:2000]
            logger.error(
                "OpenAI ChatKit session creation failed | {code} {url}\n{body}",
                code=response.status_code,
                url=sessions_url,
                body=error_body,
            )
            raise

        data: Any = response.json()
        client_secret = (((data or {}).get("client_secret") or {}).get("value"))
        if not client_secret:
            logger.error("No client_secret in response: {data}", data=data)
            raise RuntimeError("OpenAI ChatKit: client_secret.value not found in response")

        return cast(str, client_secret)


def create_chatkit_session() -> str:
    """Backward compatible alias for the service helper."""

    return create_chatkit_service_session()


