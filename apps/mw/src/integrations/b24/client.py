"""Async Bitrix24 Voximplant statistics client."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from apps.mw.src.config import get_settings

BITRIX24_ENDPOINT = "voximplant.statistic.get.json"
MAX_RETRY_ATTEMPTS = 5


def build_rest_method_url(base_url: str, user_id: int, token: str, method: str) -> str:
    """Return the fully-qualified Bitrix24 REST endpoint URL."""

    normalized = base_url.rstrip("/")
    if normalized.endswith("/rest"):
        normalized = normalized[: -len("/rest")]
    return f"{normalized}/rest/{user_id}/{token}/{method}"


def _coerce_datetime(value: str | datetime) -> str:
    """Return the ISO8601 string representation for the provided value."""

    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def _fetch_page(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
    backoff_base: float,
) -> dict[str, Any]:
    """Fetch a page of Bitrix24 calls with retry/backoff logic."""

    attempt = 0
    while True:
        logger.bind(
            event="call_export.fetch_calls",
            stage="request",
            call_id=None,
            attempt=attempt + 1,
        ).debug("Requesting Bitrix24 call list page")
        response = await client.get(url, params=params)
        if response.status_code == httpx.codes.OK:
            try:
                logger.bind(
                    event="call_export.fetch_calls",
                    stage="success",
                    call_id=None,
                    attempt=attempt + 1,
                ).debug("Received Bitrix24 call list page")
                return response.json()
            except ValueError as exc:  # pragma: no cover - defensive guard
                raise RuntimeError("Unexpected Bitrix24 payload") from exc

        if response.status_code == httpx.codes.TOO_MANY_REQUESTS or 500 <= response.status_code < 600:
            attempt += 1
            if attempt >= MAX_RETRY_ATTEMPTS:
                response.raise_for_status()

            delay = backoff_base * (2 ** (attempt - 1)) if backoff_base > 0 else 0.0
            if delay > 0:
                logger.bind(
                    event="call_export.fetch_calls",
                    stage="retry",
                    call_id=None,
                    attempt=attempt,
                    retry_delay=delay,
                ).warning("Retrying Bitrix24 page fetch")
                await asyncio.sleep(delay)
            continue

        response.raise_for_status()


async def list_calls(date_from: str | datetime, date_to: str | datetime) -> list[dict[str, Any]]:
    """Return all Voximplant calls between the provided dates."""

    settings = get_settings()
    request_url = build_rest_method_url(
        settings.b24_base_url,
        settings.b24_webhook_user_id,
        settings.b24_webhook_token,
        BITRIX24_ENDPOINT,
    )

    base_params = {
        "FILTER[DATE_FROM]": _coerce_datetime(date_from),
        "FILTER[DATE_TO]": _coerce_datetime(date_to),
    }

    backoff_base = float(settings.b24_backoff_seconds)
    rate_limit_delay = 0.0
    if settings.b24_rate_limit_rps > 0:
        rate_limit_delay = 1.0 / float(settings.b24_rate_limit_rps)

    calls: list[dict[str, Any]] = []
    start_token: str | None = None

    logger.bind(
        event="call_export.fetch_calls",
        stage="start",
        call_id=None,
        date_from=base_params["FILTER[DATE_FROM]"],
        date_to=base_params["FILTER[DATE_TO]"],
    ).info("Starting Bitrix24 call export window")

    async with httpx.AsyncClient(timeout=float(settings.request_timeout_s)) as client:
        while True:
            params = dict(base_params)
            if start_token is not None:
                params["start"] = str(start_token)

            payload = await _fetch_page(client, request_url, params, backoff_base)
            page_calls = payload.get("result") or []
            if isinstance(page_calls, list):
                calls.extend([call for call in page_calls if isinstance(call, dict)])

            next_token = payload.get("next")
            if next_token is None:
                break

            start_token = str(next_token)
            if rate_limit_delay > 0:
                logger.bind(
                    event="call_export.fetch_calls",
                    stage="throttle",
                    call_id=None,
                    attempt=0,
                    rate_limit_delay=rate_limit_delay,
                ).debug("Sleeping to respect Bitrix24 rate limit")
                await asyncio.sleep(rate_limit_delay)

    logger.bind(
        event="call_export.fetch_calls",
        stage="completed",
        call_id=None,
        total_calls=len(calls),
    ).info("Completed Bitrix24 call export window")

    return calls
