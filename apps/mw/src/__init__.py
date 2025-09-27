"""MasterMobile middleware package."""

from .integrations.b24 import list_calls as list_b24_calls

__all__ = ["list_b24_calls"]
