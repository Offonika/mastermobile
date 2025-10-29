"""Shared constants for OpenAI integrations."""

from __future__ import annotations

DEFAULT_OPENAI_HEADERS: dict[str, str] = {"OpenAI-Beta": "workflows=v1"}
"""Default headers required for interacting with OpenAI Workflows APIs."""

__all__ = ["DEFAULT_OPENAI_HEADERS"]
