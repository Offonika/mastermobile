"""Tests for the Bitrix24 list_calls helper."""
from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from apps.mw.src.config.settings import get_settings
from apps.mw.src.integrations.b24 import list_calls


@pytest.fixture(autouse=True)
def configure_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure Bitrix24-related environment variables for tests."""

    monkeypatch.setenv("B24_BASE_URL", "https://example.bitrix24.ru/rest")
    monkeypatch.setenv("B24_WEBHOOK_USER_ID", "1")
    monkeypatch.setenv("B24_WEBHOOK_TOKEN", "token")
    monkeypatch.setenv("B24_RATE_LIMIT_RPS", "2")
    monkeypatch.setenv("B24_BACKOFF_SECONDS", "5")

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def sleep_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patch asyncio.sleep to avoid real delays and capture calls."""

    mock = AsyncMock()
    monkeypatch.setattr("apps.mw.src.integrations.b24.client.asyncio.sleep", mock)
    return mock


@pytest.mark.asyncio
async def test_list_calls_paginates_and_propagates_filters(respx_mock: respx.MockRouter, sleep_mock: AsyncMock) -> None:
    """The helper fetches subsequent pages and forwards the filters to Bitrix24."""

    url = "https://example.bitrix24.ru/rest/1/token/voximplant.statistic.get.json"
    route = respx_mock.get(url).mock(
        side_effect=[
            httpx.Response(200, json={"result": [{"ID": "1"}], "next": 2}),
            httpx.Response(200, json={"result": [{"ID": "2"}]}),
        ]
    )

    calls = await list_calls("2024-08-01T00:00:00Z", "2024-08-02T00:00:00Z")

    assert calls == [{"ID": "1"}, {"ID": "2"}]
    assert route.call_count == 2

    first_params = route.calls[0].request.url.params
    assert first_params["FILTER[DATE_FROM]"] == "2024-08-01T00:00:00Z"
    assert first_params["FILTER[DATE_TO]"] == "2024-08-02T00:00:00Z"
    assert "start" not in first_params

    second_params = route.calls[1].request.url.params
    assert second_params["start"] == "2"

    # Rate limit delay is respected between paginated requests.
    assert sleep_mock.await_count == 1
    assert sleep_mock.await_args_list[0].args[0] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_list_calls_retries_on_rate_limit(respx_mock: respx.MockRouter, sleep_mock: AsyncMock) -> None:
    """HTTP 429 triggers exponential backoff and a retry."""

    url = "https://example.bitrix24.ru/rest/1/token/voximplant.statistic.get.json"
    route = respx_mock.get(url).mock(
        side_effect=[
            httpx.Response(429, json={"error": "Too many requests"}),
            httpx.Response(200, json={"result": [{"ID": "1"}]}),
        ]
    )

    calls = await list_calls("2024-08-01T00:00:00Z", "2024-08-01T23:59:59Z")

    assert calls == [{"ID": "1"}]
    assert route.call_count == 2

    # Only backoff sleep is triggered (no pagination sleep).
    assert sleep_mock.await_count == 1
    assert sleep_mock.await_args_list[0].args[0] == 5.0


@pytest.mark.asyncio
async def test_list_calls_raises_after_exhausting_retries(respx_mock: respx.MockRouter, sleep_mock: AsyncMock) -> None:
    """The helper retries on 5xx and raises after the configured limit."""

    url = "https://example.bitrix24.ru/rest/1/token/voximplant.statistic.get.json"
    respx_mock.get(url).mock(
        side_effect=[
            httpx.Response(500, json={"error": "Server error"}),
            httpx.Response(502, json={"error": "Bad gateway"}),
            httpx.Response(503, json={"error": "Unavailable"}),
            httpx.Response(504, json={"error": "Timeout"}),
            httpx.Response(500, json={"error": "Still failing"}),
        ]
    )

    with pytest.raises(httpx.HTTPStatusError):
        await list_calls("2024-08-01T00:00:00Z", "2024-08-01T23:59:59Z")

    # Four backoff intervals (attempts 1..4) before the final failure.
    durations = [await_call.args[0] for await_call in sleep_mock.await_args_list]
    assert durations == [5.0, 10.0, 20.0, 40.0]
