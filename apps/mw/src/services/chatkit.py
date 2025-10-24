"""Service helpers for interacting with OpenAI ChatKit sessions."""
from __future__ import annotations

import json
import os
from typing import Any

import httpx
from loguru import logger

from apps.mw.src.config import get_settings
from apps.mw.src.config.settings import Settings


def _get_env(name: str, default: str | None = None) -> str | None:
    """Return a normalized environment value if it is set."""

    value = os.getenv(name, default)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _build_request_payload(workflow_id: str) -> dict[str, Any]:
    """Return the payload for creating a ChatKit session."""

    payload: dict[str, Any] = {"workflow_id": workflow_id}
    model_override = _get_env("OPENAI_CHATKIT_MODEL")
    if model_override:
        payload["model"] = model_override
    return payload


def create_chatkit_session(workflow_id: str, *, settings: Settings | None = None) -> str:
    """Create an OpenAI ChatKit session via HTTP and return its client secret."""

    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise ValueError("Workflow identifier must be a non-empty string.")

    settings = settings or get_settings()

    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    base_url = _get_env("OPENAI_BASE_URL", settings.openai_base_url) or "https://api.openai.com/v1"
    url = f"{base_url.rstrip('/')}/chat.completions/sessions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    beta_header = _get_env("OPENAI_BETA_HEADER")
    if beta_header:
        headers["OpenAI-Beta"] = beta_header

    payload = _build_request_payload(workflow_id.strip())

    logger.bind(url=url).debug("Creating OpenAI ChatKit session")

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(url, headers=headers, json=payload)
    except Exception:
        logger.exception("HTTP error while creating OpenAI ChatKit session")
        raise

    if response.status_code >= 400:
        logger.error(
            "OpenAI ChatKit session creation failed",
            status_code=response.status_code,
            response_body=response.text[:2000],
        )
        response.raise_for_status()

    try:
        data = response.json()
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        logger.error("Non-JSON response from OpenAI ChatKit session API", response_body=response.text[:1000])
        raise RuntimeError("OpenAI ChatKit session API did not return JSON") from exc

    client_secret: str | None = None
    if isinstance(data, dict):
        client_secret_field = data.get("client_secret")
        if isinstance(client_secret_field, dict):
            client_secret = client_secret_field.get("value")
        elif isinstance(client_secret_field, str):
            client_secret = client_secret_field

    if not isinstance(client_secret, str) or not client_secret.strip():
        logger.error("OpenAI ChatKit session response is missing client_secret", response_data=data)
        raise ValueError("OpenAI ChatKit session API response is missing client_secret")

    return client_secret
