"""IOBridge -- interface for anything that drives the loop (CLI, Web, Mattermost)."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from core.addon import Addon

if TYPE_CHECKING:
    from core.loop import Loop

__all__ = [
    "IOBridge",
    "IORegistry",
]


class IOBridge(Addon):
    """Interface for anything that drives the loop.

    It is both a Driver (provides input, shows output) and an Addon
    (hooks into pipeline).
    """

    @abstractmethod
    def drive(self, loop: Loop) -> None:
        """Start the IO loop -- blocks until done.

        Calls loop.run() for each input received.
        """
        ...


class IORegistry:
    """Manages IO bridges with fallback."""

    def __init__(self, fallback: IOBridge) -> None:
        self._bridges: list[IOBridge] = [fallback]
        self._active: IOBridge = fallback
        self._fallback: IOBridge = fallback

    def add(self, bridge: IOBridge) -> None:
        """Register an additional IO bridge."""
        self._bridges.append(bridge)

    def set_active(self, name: str) -> bool:
        """Switch the active bridge.

        The fallback remains available if the active one fails.
        """
        for bridge in self._bridges:
            if bridge.name() == name:
                self._active = bridge
                return True
        return False

    def active(self) -> IOBridge:
        """Return the current active bridge."""
        return self._active

    def fallback(self) -> IOBridge:
        """Return the fallback bridge."""
        return self._fallback

    def reset_to_fallback(self) -> None:
        """Switch back to the fallback bridge."""
        self._active = self._fallback
