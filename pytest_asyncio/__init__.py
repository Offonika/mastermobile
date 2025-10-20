"""Minimal shim for pytest-asyncio when the dependency is unavailable."""

from __future__ import annotations

import pytest


def fixture(*args, **kwargs):
    """Delegate to :func:`pytest.fixture` to mimic pytest-asyncio behaviour."""

    return pytest.fixture(*args, **kwargs)

