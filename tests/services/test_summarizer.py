from datetime import UTC, datetime

from apps.mw.src.config import Settings
from apps.mw.src.services.storage import StorageService
from apps.mw.src.services.summarizer import CallSummarizer


def test_summarizer_handles_repeated_phrases(tmp_path) -> None:
    settings = Settings(
        LOCAL_STORAGE_DIR=str(tmp_path / "storage"),
        STORAGE_BACKEND="local",
    )
    storage = StorageService(settings=settings)
    summarizer = CallSummarizer(
        settings=settings,
        storage_service=storage,
        timestamp_provider=lambda: datetime(2024, 1, 1, tzinfo=UTC),
    )

    result = summarizer.summarize("CALL-REPEAT", "Привет! Привет! Привет!")

    assert len(result.bullets) >= 3
    assert all(isinstance(item, str) and item for item in result.bullets)
