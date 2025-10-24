"""ChatKit API endpoints exposed for widget integrations."""
from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from apps.mw.src.api.dependencies import ProblemDetailException, build_error, provide_request_id
from apps.mw.src.config import Settings, get_settings
from apps.mw.src.services.chatkit import create_chatkit_service_session
from apps.mw.src.services.chatkit_state import mark_awaiting_query
from apps.mw.src.services.state import build_store

RATE_LIMIT_MAX_REQUESTS = 5
RATE_LIMIT_WINDOW_SECONDS = 10
_RATE_LIMIT_STORE = build_store("chatkit:rate-limit")

router = APIRouter(prefix="/api/v1/chatkit", tags=["chatkit"])
__all__ = ["router"]


class ChatkitSessionResponse(BaseModel):
    """Response returned to the widget when creating a session."""

    client_secret: str = Field(..., min_length=1)


class WidgetActionRequest(BaseModel):
    """Action payload coming from the widget."""

    type: str
    name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def support_legacy_format(cls, data: Any) -> Any:
        """Normalise legacy `type` values that encode the action name."""

        if not isinstance(data, dict):
            raise ValueError("Widget action payload must be an object.")

        normalised = dict(data)

        payload = normalised.get("payload", {})
        if payload is None:
            normalised["payload"] = {}
        elif not isinstance(payload, dict):
            raise ValueError("Widget action payload must be an object.")

        raw_type = normalised.get("type")
        if isinstance(raw_type, str) and "." in raw_type and "name" not in normalised:
            prefix, _, suffix = raw_type.partition(".")
            if prefix and suffix:
                normalised["type"] = prefix
                normalised["name"] = suffix
        return normalised

class WidgetActionResponse(BaseModel):
    """Acknowledgement returned to the widget."""

    ok: bool = True
    awaiting_query: bool | None = None


def resolve_tool(action: WidgetActionRequest) -> str | None:
    """Extract the tool name from a widget action payload."""

    if action.type == "tool" and action.name:
        return action.name
    if action.type.startswith("tool."):
        return action.type.split(".", 1)[1]
    return None


def _extract_conversation_identifier(payload: dict[str, Any]) -> str | None:
    """Locate a session or thread identifier within the action payload."""

    for key in ("thread_id", "session_id", "conversation_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _rate_limit_key(identifier: str | None, client_ip: str | None) -> str:
    """Return a deduplicated key for rate limiting."""

    safe_ip = (client_ip or "").strip() or "unknown"
    if identifier:
        return f"{identifier}:{safe_ip}"
    return f"ip:{safe_ip}"


def _ensure_configuration(settings: Settings, request_id: str, *, required: tuple[str, ...]) -> None:
    """Verify that mandatory ChatKit settings are present."""

    missing: list[str] = []
    for attr in required:
        value = getattr(settings, attr, "")
        if not isinstance(value, str) or not value.strip():
            missing.append(attr.upper())
    if not missing:
        return

    logger.bind(request_id=request_id).error(
        "Missing ChatKit configuration values", missing=missing
    )
    raise ProblemDetailException(
        build_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="ChatKit configuration is incomplete",
            detail=f"Missing configuration values: {', '.join(sorted(missing))}.",
            request_id=request_id,
            type_="https://api.mastermobile.app/errors/configuration",
        )
    )


@router.post(
    "/session",
    response_model=ChatkitSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Create a ChatKit session for the widget",
)
async def create_chatkit_session(
    request_id: str = Depends(provide_request_id),
) -> ChatkitSessionResponse:
    """Create a ChatKit session and return the client secret."""

    settings = get_settings()
    _ensure_configuration(
        settings,
        request_id,
        required=("openai_api_key",),
    )

    try:
        client_secret = create_chatkit_service_session()
    except httpx.HTTPError as exc:
        logger.bind(request_id=request_id).exception("Failed to create ChatKit session")
        raise ProblemDetailException(
            build_error(
                status.HTTP_502_BAD_GATEWAY,
                title="ChatKit session creation failed",
                detail="OpenAI ChatKit API request failed.",
                request_id=request_id,
                type_="https://api.mastermobile.app/errors/openai",
            )
        ) from exc
    except RuntimeError as exc:
        logger.bind(request_id=request_id).error(
            "OpenAI ChatKit response did not include a client secret",
        )
        raise ProblemDetailException(
            build_error(
                status.HTTP_502_BAD_GATEWAY,
                title="ChatKit session creation failed",
                detail=str(exc),
                request_id=request_id,
                type_="https://api.mastermobile.app/errors/openai",
            )
        ) from exc

    logger.bind(request_id=request_id).info("Created ChatKit session for widget")
    return ChatkitSessionResponse(client_secret=client_secret)


@router.post(
    "/widget-action",
    response_model=WidgetActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept actions emitted by the widget",
)
async def handle_widget_action(
    request: Request,
    action: WidgetActionRequest,
    request_id: str = Depends(provide_request_id),
    thread_id: Annotated[str | None, Header(alias="x-chatkit-thread-id")] = None,
) -> WidgetActionResponse:
    """Acknowledge widget actions to keep the integration responsive."""

    bound_logger = logger.bind(request_id=request_id)
    client_ip = request.client.host if request.client else None
    conversation_identifier = thread_id or _extract_conversation_identifier(action.payload)
    rate_limit_key = _rate_limit_key(conversation_identifier, client_ip)

    current_count = _RATE_LIMIT_STORE.increment(
        rate_limit_key,
        ttl=RATE_LIMIT_WINDOW_SECONDS,
    )
    if current_count > RATE_LIMIT_MAX_REQUESTS:
        bound_logger.warning(
            "ChatKit widget action rate limited",
            identifier=conversation_identifier,
            client_ip=client_ip,
            count=current_count,
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit",
        )

    tool_name = resolve_tool(action)

    bound_logger.info(
        "Received ChatKit widget action",
        action_type=action.type,
        name=action.name,
        tool_name=tool_name,
    )

    if tool_name is None:
        bound_logger.warning(
            "Received unsupported ChatKit widget action",
            action_type=action.type,
            name=action.name,
        )
        return WidgetActionResponse(ok=False)

    if tool_name == "search-docs":
        if conversation_identifier:
            mark_awaiting_query(conversation_identifier)
            bound_logger.debug(
                "Marked conversation as awaiting file search query",
                conversation_id=conversation_identifier,
            )
        else:
            bound_logger.warning(
                "Received search-docs action without conversation identifier",
                payload_keys=sorted(action.payload.keys()),
            )
        return WidgetActionResponse(awaiting_query=True)

    return WidgetActionResponse()

