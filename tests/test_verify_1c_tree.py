"""Unit tests for the 1C tree verification helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/1c/verify_1c_tree.py"
_spec = importlib.util.spec_from_file_location("verify_1c_tree", MODULE_PATH)
verify_1c_tree = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(verify_1c_tree)


def test_check_kmp4_build_artifact_missing(tmp_path: Path) -> None:
    """The verification should fail when the packaged EPF is absent."""

    errors = verify_1c_tree.check_kmp4_build_artifact(tmp_path)
    assert errors
    assert "Missing build artifact" in errors[0]


def test_check_kmp4_build_artifact_size_limit(tmp_path: Path) -> None:
    """Oversized packaged artifacts must be rejected with guidance."""

    artifact = tmp_path / "build" / "1c" / "kmp4_delivery_report.epf"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"0" * 1024)

    errors = verify_1c_tree.check_kmp4_build_artifact(tmp_path, size_limit=512)
    assert errors
    assert "exceeds the 10 MiB limit" in errors[0]


def test_validate_kmp4_csv_file_rejects_forbidden_characters(tmp_path: Path) -> None:
    """Control characters outside CR/LF/TAB should be reported."""

    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(
        "#KMP4_DELIVERY_REPORT,v1\r\n"
        "order_id,title,customer_name,status_code,total_amount,currency_code,courier_id,notes,created_at,updated_at\r\n"
        "1,Test,John,NEW,10.0,RUB,7,Note,2024-01-01T00:00:00Z,2024-01-01T00:00:00Z\x01\r\n",
        encoding="utf-8",
    )

    errors = verify_1c_tree.validate_kmp4_csv_file(csv_path)
    assert errors
    assert "Forbidden control character" in errors[0]


def test_validate_kmp4_csv_file_accepts_fixture() -> None:
    """The committed sample CSV should pass structural validation."""

    fixture = (
        Path(__file__).resolve().parents[1]
        / "1c"
        / "external"
        / "kmp4_delivery_report"
        / "fixtures"
        / "valid_delivery_report.csv"
    )
    assert fixture.exists(), "Fixture missing from repository"

    errors = verify_1c_tree.validate_kmp4_csv_file(fixture)
    assert errors == []
