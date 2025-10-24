"""Service helpers for creating ChatKit sessions."""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

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


def create_chatkit_service_session() -> str:
    """Create a ChatKit session using the Chat Completions Sessions API."""

    api_key = _env("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    base_url = (_env("OPENAI_BASE_URL", "https://api.openai.com/v1") or "").rstrip("/")
    model = _env("OPENAI_CHATKIT_MODEL") or "gpt-4o-mini"

    url = f"{base_url}/chat/completions/sessions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "chat-completions",
    }
    payload_variants: list[tuple[str, dict[str, Any]]] = [
        ("default_model", {"default_model": model}),
        ("model", {"model": model}),
    ]

    with httpx.Client(timeout=20.0) as http:
        for index, (variant, payload) in enumerate(payload_variants):
            logger.debug(
                "POST {url} payload_variant={variant} payload={payload}",
                url=url,
                variant=variant,
                payload=payload,
            )

            response = http.post(url, headers=headers, json=payload)
            if response.status_code < 400:
                data: Any = response.json()
                client_secret = (((data or {}).get("client_secret") or {}).get("value"))
                if not client_secret:
                    logger.error("No client_secret in response: {data}", data=data)
                    raise RuntimeError("No client_secret in ChatKit session response")

                return cast(str, client_secret)

            error_body = (response.text or "")[:2000]
            logger.error(
                "OpenAI ChatKit session creation failed | {code} {url}\n{body}",
                code=response.status_code,
                url=url,
                body=error_body,
            )


        data: Any = response.json()
        client_secret = _extract_client_secret(data)
        if not client_secret:
            logger.error("No client_secret in response: {data}", data=data)
            raise RuntimeError("No client_secret in ChatKit session response")

        return client_secret



def create_chatkit_session() -> str:
    """Backward compatible alias for the service helper."""

    return create_chatkit_service_session()


def _extract_client_secret(payload: Any) -> str | None:
    """Return the client secret from the API payload if present."""

    if not isinstance(payload, Mapping):
        return None

    secret_payload = payload.get("client_secret")

    if isinstance(secret_payload, Mapping):
        value = secret_payload.get("value")
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None

    if isinstance(secret_payload, str):
        stripped = secret_payload.strip()
        return stripped or None

    return None


