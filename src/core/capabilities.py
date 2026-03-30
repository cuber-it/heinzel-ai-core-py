"""Provider and budget capability interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "ProviderCapabilities",
    "CapabilityProvider",
    "BudgetProvider",
]


@dataclass
class ProviderCapabilities:
    """Defines what a provider can do.

    Providers report these at start(), consumers query via dispatcher.
    """

    streaming: bool = False
    tool_use: bool = False
    vision: bool = False
    audio: bool = False
    max_tokens: int = 0
    context_window: int = 0
    provider_name: str = ""
    model_name: str = ""


# Reasoning is ALWAYS prompt-based. Fully transparent. No native reasoning.
# No ReasoningRequest. No hidden thinking tokens. Every thought visible.


@runtime_checkable
class CapabilityProvider(Protocol):
    """Optional interface providers can implement."""

    def capabilities(self) -> ProviderCapabilities: ...


@runtime_checkable
class BudgetProvider(Protocol):
    """Optional interface for addons that track budget/cost limits."""

    def budget_status(self) -> tuple[float, int, int]:
        """Returns (used_pct, total, limit)."""
        ...
