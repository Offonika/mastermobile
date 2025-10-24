#!/usr/bin/env python3
"""Ping Bitrix24 Voximplant statistics endpoint for the previous day.

Usage:
    python scripts/b24_ping.py

Required environment variables (can be provided via a `.env` file in the project root):
    B24_BASE_URL         Base URL of the Bitrix24 portal, for example
                         https://example.bitrix24.ru/rest (the script also accepts
                         https://example.bitrix24.ru)
    B24_WEBHOOK_USER_ID  Numeric identifier of the webhook user (the first number in the webhook URL)
    B24_WEBHOOK_TOKEN    Secret token part of the webhook URL

The script loads variables from .env (using python-dotenv) and sends a GET request to
`voximplant.statistic.get` covering the previous UTC day. It prints totals and a sample recording URL,
and provides actionable hints for common HTTP errors (401, 403, 429).
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from dotenv import load_dotenv

import httpx


def load_environment() -> None:
    """Load environment variables from the nearest .env file."""

    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        # Fall back to repository root if the script is executed from subdirectories.
        repo_env = Path(__file__).resolve().parents[1] / ".env"
        env_path = repo_env if repo_env.exists() else env_path

    load_dotenv(dotenv_path=env_path, override=False)


def build_request_url(base_url: str, user_id: str, token: str) -> str:
    """Construct the Bitrix24 REST endpoint URL."""

    normalized_base = base_url.rstrip("/")
    if normalized_base.endswith("/rest"):
        normalized_base = normalized_base[: -len("/rest")]
    return f"{normalized_base}/rest/{user_id}/{token}/voximplant.statistic.get.json"


def calculate_previous_day() -> tuple[str, str]:
    """Return ISO8601 timestamps representing the previous UTC day."""

    today_utc = datetime.now(UTC).date()
    previous_day = today_utc - timedelta(days=1)
    start_dt = datetime.combine(previous_day, time(0, 0, 0, tzinfo=UTC))
    end_dt = datetime.combine(previous_day, time(23, 59, 59, tzinfo=UTC))
    return start_dt.isoformat().replace("+00:00", "Z"), end_dt.isoformat().replace("+00:00", "Z")


def fetch_statistics(url: str, date_from: str, date_to: str) -> httpx.Response:
    """Perform the HTTP request and return the response object."""

    params = {
        "FILTER[DATE_FROM]": date_from,
        "FILTER[DATE_TO]": date_to,
    }

    with httpx.Client(timeout=30.0) as client:
        return client.get(url, params=params)


def handle_error(response: httpx.Response) -> None:
    """Emit a human-friendly message based on the HTTP status code and exit."""

    status = response.status_code
    hints = {
        401: "Unauthorized (401): verify B24_WEBHOOK_USER_ID and B24_WEBHOOK_TOKEN.",
        403: "Forbidden (403): check webhook permissions or IP restrictions in Bitrix24.",
        429: "Too Many Requests (429): Bitrix24 rate limit reached, retry later.",
    }
    base_message = hints.get(status, f"Request failed with status {status}.")

    try:
        payload = response.json()
    except Exception:  # pragma: no cover - best effort logging
        payload = response.text

    print(base_message, file=sys.stderr)
    if payload:
        print(f"Response: {payload}", file=sys.stderr)
    raise SystemExit(1)


def summarise_calls(payload: dict) -> tuple[int, int, str | None]:
    """Compute totals and a sample recording URL from the API payload."""

    calls = payload.get("result") or []
    if not isinstance(calls, list):
        calls = []

    calls_total = len(calls)
    recordings = [call.get("RECORD_URL") for call in calls if isinstance(call, dict) and call.get("RECORD_URL")]
    calls_with_recording = len(recordings)
    example_recording = recordings[0] if recordings else None
    return calls_total, calls_with_recording, example_recording


def main() -> None:
    load_environment()

    try:
        base_url = os.environ["B24_BASE_URL"]
        user_id = os.environ["B24_WEBHOOK_USER_ID"]
        token = os.environ["B24_WEBHOOK_TOKEN"]
    except KeyError as exc:  # pragma: no cover - essential configuration guard
        missing = exc.args[0]
        print(f"Missing required environment variable: {missing}", file=sys.stderr)
        raise SystemExit(1) from exc

    request_url = build_request_url(base_url, user_id, token)
    date_from, date_to = calculate_previous_day()

    response = fetch_statistics(request_url, date_from, date_to)
    if response.status_code != 200:
        handle_error(response)

    payload = response.json()
    calls_total, calls_with_recording, example_recording = summarise_calls(payload)

    print(f"Bitrix24 Voximplant statistics for {date_from} – {date_to}")
    print(f"calls_total: {calls_total}")
    print(f"calls_with_recording: {calls_with_recording}")
    if example_recording:
        print(f"recording_url (example): {example_recording}")
    else:
        print(
            "recording_url (example): not available — enable call recording in Bitrix24 "
            "or check webhook permissions."
        )


if __name__ == "__main__":
    main()
