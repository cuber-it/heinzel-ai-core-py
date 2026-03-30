"""MemoryCapabilities -- describes what a memory backend can do."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

__all__ = [
    "MemoryCapabilities",
    "MemoryCapabilityProvider",
]


@dataclass
class MemoryCapabilities:
    """Describes what a memory backend can do.

    Reported by each memory addon at start(), queried by other components.
    """

    name: str = ""
    can_eval: bool = False
    can_search: bool = False
    can_store: bool = False
    can_infer: bool = False
    can_execute: bool = False
    can_load: bool = False
    can_save: bool = False
    operations: list[str] = field(default_factory=list)
    description: str = ""


@runtime_checkable
class MemoryCapabilityProvider(Protocol):
    """Optional interface memory addons can implement."""

    def memory_capabilities(self) -> MemoryCapabilities: ...
