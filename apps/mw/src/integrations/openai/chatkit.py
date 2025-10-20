"""Utilities for interacting with OpenAI ChatKit sessions."""
from __future__ import annotations

from typing import Any

from openai import OpenAI

from apps.mw.src.config import get_settings


def _create_openai_client() -> OpenAI:
    """Instantiate an OpenAI client configured via application settings."""

    settings = get_settings()
    kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    if settings.openai_org:
        kwargs["organization"] = settings.openai_org
    if settings.openai_project:
        kwargs["project"] = settings.openai_project
    return OpenAI(**kwargs)


def create_chatkit_session(workflow_id: str) -> str:
    """Create a ChatKit session and return its client secret."""

    client = _create_openai_client()
    session = client.chatkit.sessions.create({"workflow": {"id": workflow_id}})

    client_secret = getattr(session, "client_secret", None)
    if client_secret is None and isinstance(session, dict):
        client_secret = session.get("client_secret")

    if not isinstance(client_secret, str) or not client_secret.strip():
        raise ValueError("OpenAI ChatKit API response did not include a client secret.")

    return client_secret
