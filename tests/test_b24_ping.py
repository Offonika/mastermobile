"""Tests for the Bitrix24 ping helper script."""

from importlib import util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "b24_ping.py"
SPEC = util.spec_from_file_location("scripts.b24_ping", MODULE_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - defensive guard for import errors
    raise RuntimeError("Failed to load scripts.b24_ping module")

b24_ping = util.module_from_spec(SPEC)
SPEC.loader.exec_module(b24_ping)


@pytest.mark.parametrize(
    ("base_url", "expected"),
    (
        ("https://example.bitrix24.ru", "https://example.bitrix24.ru/rest/1/token/voximplant.statistic.get.json"),
        ("https://example.bitrix24.ru/", "https://example.bitrix24.ru/rest/1/token/voximplant.statistic.get.json"),
        ("https://example.bitrix24.ru/rest", "https://example.bitrix24.ru/rest/1/token/voximplant.statistic.get.json"),
        ("https://example.bitrix24.ru/rest/", "https://example.bitrix24.ru/rest/1/token/voximplant.statistic.get.json"),
    ),
)
def test_build_request_url_handles_base_variants(base_url: str, expected: str) -> None:
    """The request URL must be consistent regardless of trailing `/rest` in the base."""

    actual = b24_ping.build_request_url(base_url, "1", "token")
    assert actual == expected


def test_main_prints_hint_when_no_recordings(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """When recordings are missing, the operator should see actionable guidance."""

    class DummyResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"result": [{"ID": 1}]}

    monkeypatch.setattr(b24_ping, "load_environment", lambda: None)
    monkeypatch.setattr(b24_ping, "fetch_statistics", lambda *args, **kwargs: DummyResponse())
    monkeypatch.setenv("B24_BASE_URL", "https://example.bitrix24.ru")
    monkeypatch.setenv("B24_WEBHOOK_USER_ID", "1")
    monkeypatch.setenv("B24_WEBHOOK_TOKEN", "token")

    b24_ping.main()

    captured = capsys.readouterr()
    assert "recording_url (example): not available" in captured.out
    assert "enable call recording in Bitrix24" in captured.out
