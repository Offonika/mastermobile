"""Service helpers for interacting with OpenAI ChatKit sessions."""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
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


def _build_request_payloads(workflow_id: str) -> Iterator[dict[str, Any]]:
    """Yield payload variants for creating a ChatKit session.

    OpenAI recently renamed the request contract for ChatKit sessions.
    Existing installations still rely on the legacy ``workflow_id`` field,
    while the public API now expects ``workflow``/``model`` parameters.  To
    remain backwards compatible we try a small set of payload shapes ordered by
    how the platform evolved.  Duplicates are removed to avoid redundant HTTP
    calls.
    """

    model_override = _get_env("OPENAI_CHATKIT_MODEL")
    normalized_id = workflow_id.strip()

    candidates: list[dict[str, Any]] = []

    if model_override:
        # Explicit override should be attempted first for the realtime endpoint.
        candidates.append({"model": model_override})

    if normalized_id:
        if not model_override:
            # Treat the configured workflow ID as a model name when no override is present.
            candidates.append({"model": normalized_id})

        # Legacy contracts retained for backwards compatibility.
        candidates.append({"workflow_id": normalized_id})
        candidates.append({"workflow": normalized_id})
        candidates.append({"workflow": {"id": normalized_id}})

    seen: set[str] = set()
    for payload in candidates:
        # Ensure the model override is present alongside workflow-based
        # payloads when explicitly configured.
        if model_override and "model" not in payload:
            payload = {**payload, "model": model_override}

        key = json.dumps(payload, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        yield payload


def _candidate_requests(
    base_url: str,
    headers_base: dict[str, str],
    beta_header_env: str | None,
) -> Iterator[tuple[str, dict[str, str]]]:
    """Yield candidate (url, headers) combinations for ChatKit session creation."""

    normalized_base = base_url.rstrip("/")
    urls = [
        f"{normalized_base}/realtime/sessions",
        f"{normalized_base}/chat.completions/sessions",
        f"{normalized_base}/chat/completions/sessions",
    ]

    header_variants: list[dict[str, str]] = []
    beta_candidates: list[str | None] = []

    if beta_header_env:
        beta_candidates.append(beta_header_env)
    # всегда пробуем дефолтный beta-заголовок и вариант без него
    beta_candidates.append("realtime=v1")
    beta_candidates.append("chat-completions")
    beta_candidates.append(None)

    seen: set[tuple[str | None, ...]] = set()
    for beta_value in beta_candidates:
        key = (beta_value,)
        if key in seen:
            continue
        seen.add(key)
        if beta_value:
            header_variants.append({**headers_base, "OpenAI-Beta": beta_value})
        else:
            header_variants.append(dict(headers_base))

    for url in urls:
        for headers in header_variants:
            yield url, headers


def create_chatkit_session(workflow_id: str, *, settings: Settings | None = None) -> str:
    """Create an OpenAI ChatKit session via HTTP and return its client secret."""

    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise ValueError("Workflow identifier must be a non-empty string.")

    settings = settings or get_settings()

    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    base_url = _get_env("OPENAI_BASE_URL", settings.openai_base_url) or "https://api.openai.com/v1"
    headers_base = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    beta_header = _get_env("OPENAI_BETA_HEADER")

    payload_candidates = list(_build_request_payloads(workflow_id.strip()))
    if not payload_candidates:
        raise ValueError("Could not build payload for ChatKit session request")
    last_error: Exception | None = None

    with httpx.Client(timeout=20.0) as client:
        for url, headers in _candidate_requests(base_url, headers_base, beta_header):
            for payload in payload_candidates:
                safe_headers = {
                    key: ("****" if key.lower() == "authorization" else value)
                    for key, value in headers.items()
                }
                logger.debug(
                    "ChatKit session POST {url} headers={headers} payload={payload}",
                    url=url,
                    headers=safe_headers,
                    payload=payload,
                )

                try:
                    response = client.post(url, headers=headers, json=payload)
                except Exception as exc:  # pragma: no cover - network guards
                    logger.exception(
                        "HTTP error while creating OpenAI ChatKit session at {url}",
                        url=url,
                    )
                    last_error = exc
                    continue

                if response.status_code >= 400:
                    logger.error(
                        "OpenAI ChatKit session creation failed",
                        status_code=response.status_code,
                        response_body=response.text[:2000],
                        url=url,
                        payload=payload,
                    )
                    if response.status_code in {400, 404, 405}:
                        last_error = httpx.HTTPStatusError(
                            "ChatKit session creation failed with retryable status",
                            request=response.request,
                            response=response,
                        )
                        continue
                    response.raise_for_status()

                try:
                    data = response.json()
                except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
                    logger.error(
                        "Non-JSON response from OpenAI ChatKit session API",
                        response_body=response.text[:2000],
                        url=url,
                    )
                    last_error = exc
                    continue

                client_secret: str | None = None
                if isinstance(data, dict):
                    client_secret_field = data.get("client_secret")
                    if isinstance(client_secret_field, dict):
                        client_secret = client_secret_field.get("value")
                    elif isinstance(client_secret_field, str):
                        client_secret = client_secret_field

                if not isinstance(client_secret, str) or not client_secret.strip():
                    logger.error(
                        "OpenAI ChatKit session response is missing client_secret",
                        response_data=data,
                        url=url,
                    )
                    last_error = ValueError(
                        "OpenAI ChatKit session API response is missing client_secret",
                    )
                    continue

                logger.debug("OpenAI ChatKit session created successfully at {url}", url=url)
                return client_secret

    if last_error:
        raise last_error
    raise RuntimeError("OpenAI ChatKit session API attempts exhausted without success")
