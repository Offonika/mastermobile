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
