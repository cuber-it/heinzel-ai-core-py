"""Addon interface -- the contract every addon implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from core.hooks import HookPoint

if TYPE_CHECKING:
    from core.context import Context

__all__ = [
    "AddonType",
    "Result",
    "Command",
    "Addon",
    "BaseAddon",
]


class AddonType(IntEnum):
    """Informational only -- no enforcement, any addon on any hook."""

    TOOL = 0       # UserIO, CLI, Web
    MCP = 1        # External MCP servers
    MEMORY = 2     # Prolog, Forth, Md4Minds
    FILTER = 3     # Prompt building, compaction
    PROVIDER = 4   # LLM providers
    OBSERVER = 5   # Logging, metrics, cost tracking

    def __str__(self) -> str:
        return _ADDON_TYPE_NAMES.get(self, "unknown")


_ADDON_TYPE_NAMES: dict[AddonType, str] = {
    AddonType.TOOL: "tool",
    AddonType.MCP: "mcp",
    AddonType.MEMORY: "memory",
    AddonType.FILTER: "filter",
    AddonType.PROVIDER: "provider",
    AddonType.OBSERVER: "observer",
}


@dataclass
class Result:
    """What an addon returns from handle()."""

    data: dict[str, Any] = field(default_factory=dict)
    context_update: dict[str, str] = field(default_factory=dict)
    halt: bool = False
    error: Exception | None = None


@dataclass
class Command:
    """A slash-command an addon provides."""

    name: str
    description: str
    usage: str = ""


class Addon(ABC):
    """The single interface every addon implements."""

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def type(self) -> AddonType: ...

    @abstractmethod
    def hooks(self) -> list[HookPoint]: ...

    @abstractmethod
    def handle(self, hook: HookPoint, ctx: Context) -> Result: ...

    def commands(self) -> list[Command] | None:
        return None

    def handle_command(self, cmd: str, args: str, ctx: Context) -> str:
        return ""

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


class BaseAddon(Addon):
    """Default no-op implementations for optional Addon methods.

    Embed this in your addon to avoid implementing commands/handle_command
    if not needed.
    """

    def commands(self) -> list[Command] | None:
        return None

    def handle_command(self, cmd: str, args: str, ctx: Context) -> str:
        return ""
