"""Routes integrating with OpenAI ChatKit and vector store APIs."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from loguru import logger
from openai import OpenAIError

from apps.mw.src.api.dependencies import ProblemDetailException, build_error, provide_request_id
from apps.mw.src.api.schemas import ChatkitSession, VectorStoreMetadata, VectorStoreUploadResponse
from apps.mw.src.config import Settings, get_settings
from apps.mw.src.services.chatkit import create_chatkit_session

_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

router = APIRouter(prefix="/api", tags=["openai"])


def _raise_missing_configuration(request_id: str | None, missing: Sequence[str]) -> None:
    joined = ", ".join(sorted(missing))
    raise ProblemDetailException(
        build_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="OpenAI configuration is incomplete",
            detail=f"Missing configuration values: {joined}.",
            request_id=request_id,
            type_="https://api.mastermobile.app/errors/configuration",
        )
    )


def _ensure_configuration(settings: Settings, request_id: str | None, *, require: Sequence[str]) -> None:
    missing: list[str] = []
    for key in require:
        value = getattr(settings, key)
        if not isinstance(value, str) or not value.strip():
            missing.append(key.upper())
    if missing:
        _raise_missing_configuration(request_id, missing)


def _create_openai_client(settings: Settings) -> "OpenAI":
    from openai import OpenAI

    client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    if settings.openai_org:
        client_kwargs["organization"] = settings.openai_org
    if settings.openai_project:
        client_kwargs["project"] = settings.openai_project
    return OpenAI(**client_kwargs)


@router.post(
    "/chatkit/session",
    response_model=ChatkitSession,
    status_code=status.HTTP_200_OK,
    summary="Create a ChatKit session",
)
async def create_chatkit_session(request_id: str = Depends(provide_request_id)) -> ChatkitSession:
    """Create a ChatKit session using the configured workflow identifier."""

    settings = get_settings()
    _ensure_configuration(settings, request_id, require=("openai_api_key", "openai_workflow_id"))

    try:
        client_secret = create_chatkit_session(settings.openai_workflow_id)
    except OpenAIError as exc:
        logger.bind(request_id=request_id).exception("Failed to create OpenAI ChatKit session")
        raise ProblemDetailException(
            build_error(
                status.HTTP_502_BAD_GATEWAY,
                title="ChatKit session creation failed",
                detail="OpenAI ChatKit API request failed.",
                request_id=request_id,
                type_="https://api.mastermobile.app/errors/openai",
            )
        ) from exc
    except ValueError as exc:
        logger.bind(request_id=request_id).error(
            "OpenAI ChatKit session response is missing client secret",
        )
        raise ProblemDetailException(
            build_error(
                status.HTTP_502_BAD_GATEWAY,
                title="ChatKit session creation failed",
                detail=str(exc),
                request_id=request_id,
                type_="https://api.mastermobile.app/errors/openai",
            )
        )

    logger.bind(request_id=request_id).info("Created OpenAI ChatKit session")
    return ChatkitSession(client_secret=client_secret)


@router.post(
    "/vector-store/upload",
    response_model=VectorStoreUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload a document to the vector store",
)
async def upload_to_vector_store(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    dept: str | None = Form(None),
    version: str | None = Form(None),
    updated_at: str | None = Form(None),
    source: str = Form("manual"),
    request_id: str = Depends(provide_request_id),
) -> VectorStoreUploadResponse:
    """Upload a document and its metadata to the configured OpenAI vector store."""

    settings = get_settings()
    _ensure_configuration(
        settings,
        request_id,
        require=("openai_api_key", "openai_vector_store_id"),
    )

    content_type = (file.content_type or "").strip().lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise ProblemDetailException(
            build_error(
                status.HTTP_400_BAD_REQUEST,
                title="Unsupported document type",
                detail="Only PDF, DOC and DOCX files are permitted.",
                request_id=request_id,
                type_="https://api.mastermobile.app/errors/validation",
            )
        )

    filename = file.filename or "document"
    normalized_title = (title or filename).strip() or filename
    normalized_source = (source or "manual").strip() or "manual"

    metadata_model = VectorStoreMetadata(
        title=normalized_title,
        dept=dept.strip() if isinstance(dept, str) and dept.strip() else None,
        version=version.strip() if isinstance(version, str) and version.strip() else None,
        updated_at=updated_at.strip() if isinstance(updated_at, str) and updated_at.strip() else None,
        source=normalized_source,
    )

    content = await file.read()
    if not content:
        raise ProblemDetailException(
            build_error(
                status.HTTP_400_BAD_REQUEST,
                title="Empty document",
                detail="Uploaded file does not contain any data.",
                request_id=request_id,
                type_="https://api.mastermobile.app/errors/validation",
            )
        )

    client = _create_openai_client(settings)
    payload = {
        "file_name": filename,
        "content": content,
    }
    metadata_payload = metadata_model.model_dump(exclude_none=True)

    try:
        client.vector_stores.files.upload(
            vector_store_id=settings.openai_vector_store_id,
            file=payload,
            metadata=metadata_payload,
        )
    except OpenAIError as exc:
        logger.bind(request_id=request_id, filename=filename).exception(
            "Failed to upload document to OpenAI vector store",
        )
        raise ProblemDetailException(
            build_error(
                status.HTTP_502_BAD_GATEWAY,
                title="Vector store upload failed",
                detail="OpenAI vector store API request failed.",
                request_id=request_id,
                type_="https://api.mastermobile.app/errors/openai",
            )
        ) from exc

    logger.bind(request_id=request_id, filename=filename).info(
        "Uploaded document to OpenAI vector store",
    )
    return VectorStoreUploadResponse(status="ok", filename=filename, metadata=metadata_model)
