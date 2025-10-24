"""Service helpers for interacting with OpenAI ChatKit sessions."""
from __future__ import annotations

from typing import Any, cast

from openai import OpenAI

from apps.mw.src.config import get_settings
from apps.mw.src.config.settings import Settings


def _create_openai_client(settings: Settings | None = None) -> OpenAI:
    """Instantiate an OpenAI client configured from application settings."""

    settings = settings or get_settings()

    client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    if settings.openai_org:
        client_kwargs["organization"] = settings.openai_org
    if settings.openai_project:
        client_kwargs["project"] = settings.openai_project

    return OpenAI(**client_kwargs)


def create_chatkit_session(workflow_id: str, *, settings: Settings | None = None) -> str:
    """Create an OpenAI ChatKit session and return its client secret."""

    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise ValueError("Workflow identifier must be a non-empty string.")

    client = _create_openai_client(settings)
    chatkit = cast(Any, client).chatkit
    session = chatkit.sessions.create({"workflow": {"id": workflow_id}})

    client_secret = getattr(session, "client_secret", None)
    if client_secret is None and isinstance(session, dict):
        client_secret = session.get("client_secret")

    if not isinstance(client_secret, str) or not client_secret.strip():
        raise ValueError("OpenAI ChatKit API response did not include a client secret.")

    return client_secret
