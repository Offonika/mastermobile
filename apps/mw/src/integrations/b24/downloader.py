"""Utilities for downloading Bitrix24 call recordings."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
from loguru import logger

from apps.mw.src.config import get_settings

from .client import MAX_RETRY_ATTEMPTS, build_rest_method_url

RECORDING_ENDPOINT = "telephony.recording.get"


def _compute_backoff_delay(base: float, attempt: int) -> float:
    """Return exponential backoff delay for the given attempt index."""

    if base <= 0:
        return 0.0
    return base * (2 ** (attempt - 1))


async def stream_recording(call_id: str, record_id: str | None = None) -> AsyncIterator[bytes]:
    """Yield chunks of a Bitrix24 call recording applying retry/backoff policy."""

    settings = get_settings()
    request_url = build_rest_method_url(
        settings.b24_base_url,
        settings.b24_webhook_user_id,
        settings.b24_webhook_token,
        RECORDING_ENDPOINT,
    )

    params: dict[str, str] = {"CALL_ID": call_id}
    if record_id is not None:
        params["RECORD_ID"] = record_id

    backoff_base = float(settings.b24_backoff_seconds)

    async with httpx.AsyncClient(timeout=float(settings.request_timeout_s)) as client:
        attempt = 0
        while True:
            should_retry = False
            delay = 0.0
            try:
                logger.bind(
                    event="call_export.recording",
                    stage="request",
                    call_id=call_id,
                    attempt=attempt + 1,
                    record_id=record_id,
                ).debug("Requesting Bitrix24 call recording stream")
                async with client.stream("GET", request_url, params=params) as response:
                    if response.status_code == httpx.codes.OK:
                        try:
                            async for chunk in response.aiter_bytes():
                                if chunk:
                                    yield chunk
                            logger.bind(
                                event="call_export.recording",
                                stage="completed",
                                call_id=call_id,
                                attempt=attempt + 1,
                                record_id=record_id,
                            ).info("Completed Bitrix24 call recording stream")
                            return
                        except httpx.HTTPError:
                            attempt += 1
                            if attempt >= MAX_RETRY_ATTEMPTS:
                                raise
                            delay = _compute_backoff_delay(backoff_base, attempt)
                            should_retry = True
                    elif (
                        response.status_code == httpx.codes.TOO_MANY_REQUESTS
                        or 500 <= response.status_code < 600
                    ):
                        attempt += 1
                        if attempt >= MAX_RETRY_ATTEMPTS:
                            response.raise_for_status()
                        delay = _compute_backoff_delay(backoff_base, attempt)
                        logger.bind(
                            event="call_export.recording",
                            stage="retry",
                            call_id=call_id,
                            attempt=attempt,
                            record_id=record_id,
                            retry_delay=delay,
                        ).warning("Retrying Bitrix24 call recording stream")
                        should_retry = True
                    else:
                        logger.bind(
                            event="call_export.recording",
                            stage="failure",
                            call_id=call_id,
                            attempt=attempt + 1,
                            record_id=record_id,
                            status_code=response.status_code,
                        ).error("Received unexpected Bitrix24 response")
                        response.raise_for_status()
                        return
            except httpx.RequestError:
                attempt += 1
                if attempt >= MAX_RETRY_ATTEMPTS:
                    raise
                delay = _compute_backoff_delay(backoff_base, attempt)
                logger.bind(
                    event="call_export.recording",
                    stage="retry",
                    call_id=call_id,
                    attempt=attempt,
                    record_id=record_id,
                    retry_delay=delay,
                ).warning("Retrying Bitrix24 call recording stream after transport error")
                should_retry = True

            if should_retry:
                if delay > 0:
                    await asyncio.sleep(delay)
                continue

            # If we reach this point it means the response raised a non-retryable
            # error and the exception has already been propagated.
            return

