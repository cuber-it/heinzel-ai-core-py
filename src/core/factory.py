"""Factory -- config-driven addon loading via builder registry."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

from core.addon import Addon
from core.config import Config
from core.dispatcher import Dispatcher

__all__ = [
    "Factory",
    "AddonEntry",
    "BuildResult",
    "AddonBuilder",
    "register_addon_builder",
    "PFLICHT_ADDONS",
    "OPTIONAL_ADDONS",
    "is_addon_enabled",
    "permissions_path",
]

# Type alias for addon builder functions
AddonBuilder = Callable[[Config, Dispatcher], tuple[Addon, int]]


@dataclass
class AddonEntry:
    """A factory-produced addon with its priority."""

    addon: Addon
    priority: int
    name: str


@dataclass
class BuildResult:
    """Contains everything the factory produced."""

    entries: list[AddonEntry] = field(default_factory=list)

    # References for post-build wiring (main connects these)
    cli_bridge: Any = None
    mcp_manager: Any = None
    compaction: Any = None
    reasoning: Any = None
    facts_layer: Any = None
    cost_guard: Any = None


# Registry of addon builders -- populated by addons package via register
_addon_builders: dict[str, AddonBuilder] = {}


def register_addon_builder(name: str, builder: AddonBuilder) -> None:
    _addon_builders[name] = builder


# Pflicht addons are always loaded, in this order
PFLICHT_ADDONS: list[str] = [
    "cli",        # IO -- must be first
    "logger",     # actually optional, but harmless
    "prompt",     # prompt composition + awareness + skills
    "recovery",   # error handling
    "commands",   # universal command handler
    "costguard",  # budget enforcement
    "provider",   # LLM provider -- must exist
]

# Optional addons and their config toggles
OPTIONAL_ADDONS: list[str] = [
    "reasoning",
    "memory_composer",
    "compaction",
    "file_upload",
    "websearch",
    "chatlog",
    "transcript",
    "mcp_manager",
    "heartbeat",
    "cognitive_memory",
]


def is_addon_enabled(config: Config, name: str) -> bool:
    return config.addons.is_enabled(name)


class Factory:
    """Builds addons and wires them together based on config.

    Pflicht-addons are always created. Optional addons depend on config.
    """

    def __init__(self, config: Config, dispatcher: Dispatcher) -> None:
        self.config = config
        self.dispatcher = dispatcher

        # Post-build references for addons that need cross-wiring
        self.loop: Any = None
        self.cli_bridge: Any = None
        self.mcp_manager: Any = None
        self.compaction: Any = None
        self.reasoning: Any = None
        self.facts_layer: Any = None

    def build(self) -> BuildResult:
        result = BuildResult()

        # Pflicht addons -- always loaded
        for name in PFLICHT_ADDONS:
            # Logger is actually optional
            if name == "logger" and not is_addon_enabled(self.config, name):
                continue

            builder = _addon_builders.get(name)
            if builder is None:
                raise RuntimeError(f"pflicht addon {name!r} has no registered builder")

            addon, priority = builder(self.config, self.dispatcher)
            result.entries.append(AddonEntry(addon=addon, priority=priority, name=name))

        # Optional addons -- only if enabled
        for name in OPTIONAL_ADDONS:
            if not is_addon_enabled(self.config, name):
                continue

            builder = _addon_builders.get(name)
            if builder is None:
                continue  # optional -- skip if no builder registered

            addon, priority = builder(self.config, self.dispatcher)
            result.entries.append(AddonEntry(addon=addon, priority=priority, name=name))

        return result


def permissions_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".neo-heinzel", "permissions.yaml")
