"""Helpers for invoking OpenAI Agent Builder workflows."""
from __future__ import annotations

import json
from typing import Any, Dict, Mapping, MutableMapping, Sequence

import httpx
from loguru import logger
from openai import AsyncOpenAI, OpenAIError

from apps.mw.src.config import Settings

__all__ = [
    "WorkflowInvocationError",
    "forward_widget_action_to_workflow",
]


class WorkflowInvocationError(RuntimeError):
    """Raised when an OpenAI workflow invocation fails."""


_CLIENT_CACHE: MutableMapping[tuple[str, str | None, str | None, str | None], AsyncOpenAI] = {}


def _to_mapping(payload: Any) -> Mapping[str, Any]:
    """Best-effort conversion of OpenAI response payloads to a mapping."""

    if hasattr(payload, "model_dump"):
        try:
            data = payload.model_dump()
            if isinstance(data, Mapping):
                return data
        except TypeError:  # pragma: no cover - defensive guard
            pass
    if hasattr(payload, "to_dict"):
        try:
            data = payload.to_dict()
            if isinstance(data, Mapping):
                return data
        except TypeError:  # pragma: no cover - defensive guard
            pass
    if isinstance(payload, Mapping):
        return payload
    return {}


def _extract_text_from_node(node: Any) -> str | None:
    """Return the first textual reply contained within the payload."""

    if isinstance(node, str):
        stripped = node.strip()
        return stripped or None

    if isinstance(node, Mapping):
        node_type = node.get("type")
        text = node.get("text")
        if isinstance(text, str):
            if node_type is None or "text" in node_type or "message" in node_type:
                stripped_text = text.strip()
                if stripped_text:
                    return stripped_text

        for key in ("content", "output", "outputs", "messages", "response", "data"):
            value = node.get(key)
            if value is None:
                continue
            extracted = _extract_text_from_node(value)
            if extracted:
                return extracted

        for key, value in node.items():
            if key in {"metadata", "annotations", "context"}:
                continue
            if isinstance(value, (Mapping, Sequence)) and not isinstance(
                value, (str, bytes, bytearray)
            ):
                extracted = _extract_text_from_node(value)
                if extracted:
                    return extracted

    elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
        for item in node:
            extracted = _extract_text_from_node(item)
            if extracted:
                return extracted

    return None


def _normalise(value: str | None) -> str | None:
    """Return a stripped string or ``None`` when empty."""

    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _client_cache_key(settings: Settings) -> tuple[str, str | None, str | None, str | None]:
    """Build a cache key for the AsyncOpenAI client."""

    return (
        (settings.openai_api_key or "").strip(),
        _normalise(settings.openai_base_url),
        _normalise(settings.openai_org),
        _normalise(settings.openai_project),
    )


def _get_async_openai_client(settings: Settings) -> AsyncOpenAI:
    """Return a cached :class:`AsyncOpenAI` client configured from settings."""

    cache_key = _client_cache_key(settings)
    api_key = cache_key[0]
    if not api_key:
        raise WorkflowInvocationError("OpenAI API key is not configured.")

    client = _CLIENT_CACHE.get(cache_key)
    if client is None:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=cache_key[1],
            organization=cache_key[2],
            project=cache_key[3],
        )
        _CLIENT_CACHE[cache_key] = client
    return client


def _build_metadata(entries: Mapping[str, str | None]) -> Dict[str, str]:
    """Construct metadata respecting OpenAI requirements."""

    metadata: Dict[str, str] = {}
    for key, value in entries.items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        metadata[key] = text[:512]
        if len(metadata) >= 16:
            break
    return metadata


async def forward_widget_action_to_workflow(
    *,
    settings: Settings,
    action: Mapping[str, Any],
    request_id: str,
    tool_name: str | None,
    thread_id: str | None,
    conversation_identifier: str | None,
    origin: str | None,
) -> str | None:
    """Send a widget action payload to the configured workflow.

    Returns the first textual snippet produced by the workflow when available.
    """

    workflow_id = (settings.openai_workflow_id or "").strip()
    if not workflow_id:
        raise WorkflowInvocationError("OpenAI workflow identifier is not configured.")

    client = _get_async_openai_client(settings)

    context = {
        "request_id": request_id,
        "tool_name": tool_name,
        "thread_id": thread_id,
        "conversation_identifier": conversation_identifier,
        "origin": origin,
    }

    payload = {
        "event": "chatkit.widget_action",
        "action": dict(action),
        "context": {key: value for key, value in context.items() if value is not None},
    }

    message_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    metadata = _build_metadata(
        {
            "request_id": request_id,
            "tool_name": tool_name,
            "thread_id": thread_id,
            "conversation_id": conversation_identifier,
        }
    )

    try:
        response = await client.responses.create(
            model=workflow_id,
            input=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": message_text,
                        }
                    ],
                }
            ],
            metadata=metadata or None,
        )
    except (OpenAIError, httpx.HTTPError) as exc:  # pragma: no cover - network errors
        logger.bind(request_id=request_id, tool_name=tool_name).exception(
            "Failed to forward ChatKit widget action to OpenAI workflow",
        )
        raise WorkflowInvocationError("Failed to invoke OpenAI workflow") from exc

    response_payload = _to_mapping(response)
    extracted_text = _extract_text_from_node(response_payload)

    logger.bind(request_id=request_id, tool_name=tool_name).debug(
        "Forwarded ChatKit widget action to OpenAI workflow",
        has_response=bool(extracted_text),
    )

    return extracted_text

