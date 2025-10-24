"""State machine for Walking Warehouse order statuses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from apps.mw.src.api.schemas.ww import WWOrderStatus


class InvalidOrderStatusTransitionError(RuntimeError):
    """Raised when a status transition violates the workflow."""

    def __init__(self, current: WWOrderStatus, new: WWOrderStatus) -> None:
        self.current = current
        self.new = new
        super().__init__(f"Cannot transition order status from {current} to {new}.")


@dataclass
class OrderStateMachine:
    """Encapsulates allowed transitions between order statuses."""

    current: WWOrderStatus

    _ALLOWED_TRANSITIONS: ClassVar[dict[WWOrderStatus, set[WWOrderStatus]]] = {
        WWOrderStatus.NEW: {WWOrderStatus.ASSIGNED, WWOrderStatus.REJECTED},
        WWOrderStatus.ASSIGNED: {
            WWOrderStatus.IN_TRANSIT,
            WWOrderStatus.DECLINED,
            WWOrderStatus.REJECTED,
        },
        WWOrderStatus.IN_TRANSIT: {WWOrderStatus.DONE, WWOrderStatus.REJECTED},
        WWOrderStatus.DONE: set(),
        WWOrderStatus.REJECTED: set(),
        WWOrderStatus.DECLINED: {WWOrderStatus.NEW},
    }

    def ensure_transition(self, new: WWOrderStatus) -> None:
        """Validate transition to a new status."""

        if new == self.current:
            return

        allowed = self._ALLOWED_TRANSITIONS.get(self.current, set())
        if new not in allowed:
            raise InvalidOrderStatusTransitionError(self.current, new)

        self.current = new

    @classmethod
    def from_raw(cls, status: WWOrderStatus | str) -> OrderStateMachine:
        """Create a state machine from a raw stored status value."""

        if isinstance(status, WWOrderStatus):
            return cls(current=status)

        return cls(current=WWOrderStatus(status))
