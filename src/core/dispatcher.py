"""Dispatcher -- addon registration and hook-based dispatch."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.addon import Addon, Command, Result
from core.capabilities import CapabilityProvider, ProviderCapabilities
from core.hooks import HOOK_COUNT, HookPoint

if TYPE_CHECKING:
    from core.context import Context

__all__ = ["Dispatcher"]

logger = logging.getLogger(__name__)


@dataclass
class _Registration:
    addon: Addon
    priority: int


class Dispatcher:
    """Manages addon registrations and dispatches hooks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hooks: list[list[_Registration]] = [[] for _ in range(HOOK_COUNT)]
        self._addons: dict[str, _Registration] = {}

    def register(self, addon: Addon, priority: int) -> None:
        """Add an addon and wire it to its declared hooks."""
        with self._lock:
            name = addon.name()
            if name in self._addons:
                raise ValueError(f"addon {name!r} already registered")

            self._addons[name] = _Registration(addon=addon, priority=priority)

            for hook in addon.hooks():
                if 0 <= hook < HOOK_COUNT:
                    self._hooks[hook].append(_Registration(addon=addon, priority=priority))
                    self._hooks[hook].sort(key=lambda reg: reg.priority)

    def register_at(self, addon: Addon, priority: int, *hooks: HookPoint) -> None:
        """Add an addon to specific hooks (ignoring addon's hooks() method)."""
        with self._lock:
            name = addon.name()
            self._addons[name] = _Registration(addon=addon, priority=priority)

            for hook in hooks:
                if 0 <= hook < HOOK_COUNT:
                    self._hooks[hook].append(_Registration(addon=addon, priority=priority))
                    self._hooks[hook].sort(key=lambda reg: reg.priority)

    def unregister(self, name: str) -> None:
        """Remove an addon from all hooks."""
        with self._lock:
            self._addons.pop(name, None)
            for hook_index in range(HOOK_COUNT):
                self._hooks[hook_index] = [
                    reg for reg in self._hooks[hook_index]
                    if reg.addon.name() != name
                ]

    def dispatch(self, hook: HookPoint, ctx: Context) -> list[Result]:
        """Fire a hook and call all registered addons in priority order.

        Returns combined results. Stops if any addon sets halt=True.
        """
        with self._lock:
            regs = list(self._hooks[hook])

        results: list[Result] = []
        for reg in regs:
            result = reg.addon.handle(hook, ctx)

            if result.context_update:
                for key, value in result.context_update.items():
                    ctx.set(key, value)

            results.append(result)

            if result.halt:
                ctx.halt = True
                break

            if result.error is not None:
                ctx.error = result.error

        return results

    def get_addon(self, name: str) -> tuple[Addon | None, bool]:
        with self._lock:
            entry = self._addons.get(name)
            if entry is None:
                return None, False
            return entry.addon, True

    def list_addons(self) -> list[str]:
        with self._lock:
            return sorted(self._addons.keys())

    def dispatch_command(self, cmd: str, args: str, ctx: Context) -> tuple[str, bool]:
        """Route a slash-command to the right addon. Returns (response, handled)."""
        with self._lock:
            target: Addon | None = None
            for entry in self._addons.values():
                addon_cmds = entry.addon.commands()
                if addon_cmds:
                    for addon_cmd in addon_cmds:
                        if addon_cmd.name == cmd:
                            target = entry.addon
                            break
                if target is not None:
                    break

        if target is not None:
            return target.handle_command(cmd, args, ctx), True
        return "", False

    def all_commands(self) -> list[Command]:
        with self._lock:
            commands: list[Command] = []
            for entry in self._addons.values():
                cmds = entry.addon.commands()
                if cmds is not None:
                    commands.extend(cmds)
            return commands

    def hook_subscribers(self, hook: HookPoint) -> list[str]:
        with self._lock:
            return [reg.addon.name() for reg in self._hooks[hook]]

    def get_provider_capabilities(self) -> ProviderCapabilities | None:
        """Find the active provider and return its capabilities."""
        with self._lock:
            for entry in self._addons.values():
                if isinstance(entry.addon, CapabilityProvider):
                    return entry.addon.capabilities()
        return None

    def start_all(self) -> None:
        with self._lock:
            addons_to_start = list(self._addons.items())

        for name, entry in addons_to_start:
            try:
                entry.addon.start()
            except Exception as exc:
                raise RuntimeError(f"addon {name!r} start failed: {exc}") from exc

    def stop_all(self) -> None:
        """Stop all registered addons in reverse priority order.

        High-priority addons (higher number) stop first,
        low-priority (e.g. providers) stop last.
        Each addon gets 5 seconds to stop before we log and move on.
        """
        with self._lock:
            entries = list(self._addons.values())

        entries.sort(key=lambda entry: entry.priority, reverse=True)

        for entry in entries:
            name = entry.addon.name()
            done_event = threading.Event()
            error_holder: list[Exception] = []

            def _stop(addon: Addon = entry.addon) -> None:
                try:
                    addon.stop()
                except Exception as exc:
                    error_holder.append(exc)
                finally:
                    done_event.set()

            thread = threading.Thread(target=_stop, daemon=True)
            thread.start()

            if not done_event.wait(timeout=5.0):
                logger.warning("addon %r stop timed out after 5s, continuing", name)
            elif error_holder:
                logger.warning("addon %r stop error: %s", name, error_holder[0])
