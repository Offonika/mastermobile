"""Service helpers for creating ChatKit sessions."""
from __future__ import annotations

import os
from typing import Any, cast

import httpx
from loguru import logger

__all__ = ["create_chatkit_service_session", "create_chatkit_session"]


def _env(name: str, default: str | None = None) -> str | None:
    """Return a normalised environment value."""

    value = os.getenv(name, default)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _beta_headers(api_key: str) -> dict[str, str]:
    """Return headers required for beta Chat Completions endpoints."""

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "chat-completions",
    }


def _resolve_model() -> str:
    """Resolve the model used to bootstrap ChatKit sessions."""

    return (
        _env("OPENAI_CHATKIT_MODEL")
        or _env("OPENAI_MODEL")
        or "gpt-4o-mini"
    )


def create_chatkit_service_session() -> str:
    """Create a ChatKit session using the Chat Completions Sessions API."""

    api_key = _env("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    base_url = (_env("OPENAI_BASE_URL", "https://api.openai.com/v1") or "").rstrip("/")
    sessions_url = f"{base_url}/chat/completions/sessions"
    headers = _beta_headers(api_key)

    model = _resolve_model()


    with httpx.Client(timeout=20.0) as http:
        payload = {"model": model}

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


