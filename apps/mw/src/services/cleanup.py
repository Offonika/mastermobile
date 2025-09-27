"""Background routines for maintaining storage hygiene."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from loguru import logger

from apps.mw.src.config import Settings, get_settings
from apps.mw.src.services.storage import CleanupReport, StorageService


class StorageCleanupRunner:
    """Periodically remove expired recordings, transcripts and summaries."""

    def __init__(
        self,
        *,
        storage_service: StorageService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._storage = storage_service or StorageService(settings=self._settings)
        self._interval_seconds = max(1, int(self._settings.storage_cleanup_interval_hours * 3600))

    async def run_periodic(self) -> None:
        """Run the cleanup loop until the task is cancelled."""

        while True:
            await self._run_once_with_logging()
            try:
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:  # pragma: no cover - cooperative cancellation
                raise

    async def run_once(self, *, now: datetime | None = None) -> CleanupReport:
        """Execute a single cleanup sweep and return the report."""

        return await asyncio.to_thread(self._storage.cleanup_expired_assets, now=now)

    async def _run_once_with_logging(self) -> None:
        try:
            report = await self.run_once()
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Storage cleanup run failed")
            return

        context: dict[str, Any] = {
            "local_removed": len(report.removed_local_paths),
            "s3_removed": len(report.removed_s3_keys),
            "total_removed": report.total_removed,
        }
        logger.bind(**context).info("Storage cleanup completed")
