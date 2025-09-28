"""Mappings and helpers for Walking Warehouse status codes."""

from __future__ import annotations

from typing import Final

from apps.mw.src.api.schemas.ww import WWOrderStatus


class UnknownWWStatusError(ValueError):
    """Raised when a Walking Warehouse status cannot be mapped to KMP4."""


WW_TO_KMP4_STATUS: Final[dict[WWOrderStatus, str]] = {
    WWOrderStatus.NEW: "new",
    WWOrderStatus.ASSIGNED: "assigned_to_courier",
    WWOrderStatus.IN_TRANSIT: "courier_on_route",
    WWOrderStatus.DONE: "completed",
    WWOrderStatus.REJECTED: "cancelled_by_manager",
    WWOrderStatus.DECLINED: "declined_by_courier",
}


def map_ww_status_to_kmp4(status: WWOrderStatus | str) -> str:
    """Translate a Walking Warehouse status into the KMP4 status code."""

    if isinstance(status, WWOrderStatus):
        status_enum = status
    else:
        try:
            status_enum = WWOrderStatus(status)
        except ValueError as exc:  # pragma: no cover - ValueError is re-raised with context
            raise UnknownWWStatusError(
                f"Unsupported Walking Warehouse status: {status!r}."
            ) from exc

    try:
        return WW_TO_KMP4_STATUS[status_enum]
    except KeyError as exc:  # pragma: no cover - defensive guard for unmapped statuses
        raise UnknownWWStatusError(
            f"No KMP4 status mapping defined for {status_enum.value!r}."
        ) from exc


__all__ = ["WW_TO_KMP4_STATUS", "map_ww_status_to_kmp4", "UnknownWWStatusError"]
