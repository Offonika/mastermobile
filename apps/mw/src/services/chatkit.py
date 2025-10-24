"""Service helpers for interacting with OpenAI ChatKit sessions."""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

from loguru import logger
from openai import OpenAI, OpenAIError

from apps.mw.src.config import get_settings
from apps.mw.src.config.settings import Settings


def _get_env(name: str, default: str | None = None) -> str | None:
    """Return a normalized environment value if it is set."""

    value = os.getenv(name, default)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _build_session_payloads(workflow_id: str) -> list[dict[str, Any]]:
    """Construct session payloads for the realtime client secret endpoint."""

    model_override = _get_env("OPENAI_CHATKIT_MODEL")
    voice_override = _get_env("OPENAI_CHATKIT_VOICE")
    normalized_id = workflow_id.strip()

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _attach_voice(payload: dict[str, Any]) -> dict[str, Any]:
        if not voice_override:
            return payload
        audio_cfg = {"output": {"voice": voice_override}}
        existing_audio = payload.get("audio")
        if isinstance(existing_audio, dict):
            audio_cfg = {**existing_audio, "output": {**existing_audio.get("output", {}), "voice": voice_override}}
        return {**payload, "audio": audio_cfg}

    def _append_model(candidate_model: str) -> None:
        if not candidate_model:
            return
        session_payload = _attach_voice({"type": "realtime", "model": candidate_model})
        key = json.dumps(session_payload, sort_keys=True)
        if key in seen:
            return
        seen.add(key)
        candidates.append(session_payload)

    if model_override:
        _append_model(model_override)

    if normalized_id and (not model_override or model_override != normalized_id):
        _append_model(normalized_id)

    return candidates


def _beta_header_candidates(beta_header_env: str | None) -> Iterator[str | None]:
    """Yield beta header values to try when calling the realtime API."""

    seen: set[str | None] = set()
    ordered_candidates: tuple[str | None, ...]
    if beta_header_env:
        ordered_candidates = (beta_header_env, "realtime=v1", None)
    else:
        ordered_candidates = ("realtime=v1", None)

    for candidate in ordered_candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        yield candidate


def create_chatkit_session(workflow_id: str, *, settings: Settings | None = None) -> str:
    """Create an OpenAI ChatKit session via HTTP and return its client secret."""

    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise ValueError("Workflow identifier must be a non-empty string.")

    settings = settings or get_settings()

    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    base_url = _get_env("OPENAI_BASE_URL", settings.openai_base_url) or "https://api.openai.com/v1"
    session_candidates = _build_session_payloads(workflow_id.strip())
    if not session_candidates:
        raise ValueError("Could not build payload for ChatKit session request")

    beta_header_env = _get_env("OPENAI_BETA_HEADER")
    last_error: Exception | None = None

    client_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "base_url": base_url,
    }
    organization = _get_env("OPENAI_ORG", settings.openai_org)
    project = _get_env("OPENAI_PROJECT", settings.openai_project)
    if organization:
        client_kwargs["organization"] = organization
    if project:
        client_kwargs["project"] = project

    client = OpenAI(**client_kwargs)
    try:
        for beta_header in _beta_header_candidates(beta_header_env):
            extra_headers = {"OpenAI-Beta": beta_header} if beta_header else None
            for payload in session_candidates:
                logger.debug(
                    "Attempting to create OpenAI ChatKit client secret",
                    beta_header=beta_header,
                    session_payload=payload,
                )
                try:
                    response = client.realtime.client_secrets.create(
                        session=payload,
                        extra_headers=extra_headers,
                    )
                except OpenAIError as exc:
                    logger.error(
                        "OpenAI ChatKit client secret creation failed",
                        beta_header=beta_header,
                        session_payload=payload,
                    )
                    last_error = exc
                    continue

                client_secret = getattr(response, "value", None)
                if isinstance(client_secret, str) and client_secret.strip():
                    logger.debug("OpenAI ChatKit client secret created successfully")
                    return client_secret

                logger.error(
                    "OpenAI ChatKit client secret response is missing value",
                    response_data=response,
                )
                last_error = ValueError(
                    "OpenAI ChatKit client secret response is missing value",
                )
    finally:
        try:
            client.close()
        except Exception:  # pragma: no cover - defensive cleanup
            logger.exception("Failed to close OpenAI client after ChatKit session attempt")

    if last_error:
        raise last_error
    raise RuntimeError("OpenAI ChatKit client secret attempts exhausted without success")
