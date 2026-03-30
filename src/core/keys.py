"""Context key registry -- typed, validated, documented.

Every key must be registered before use. Unregistered keys raise KeyError.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

__all__ = [
    "KeyDef",
    "KeyRegistry",
    "register_key",
    "must_get_key",
    "is_registered",
    "all_keys",
    "KEY_NEEDS_RERUN",
    "KEY_INTERNAL_QUERY",
    "KEY_STRATEGY_OVERRIDE",
    "KEY_THINKING",
]


@dataclass(frozen=True)
class KeyDef:
    """Defines a context key with metadata."""

    name: str
    description: str
    type: str  # expected Python type as string
    category: str  # core, flow, output, resource, token, user, memory, internal, compaction


class KeyRegistry:
    """Holds all registered context keys."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: dict[str, KeyDef] = {}

    def register(self, key_def: KeyDef) -> str:
        with self._lock:
            if key_def.name in self._keys:
                raise RuntimeError(f"context key {key_def.name!r} already registered")
            self._keys[key_def.name] = key_def
        return key_def.name

    def must_get(self, name: str) -> KeyDef:
        with self._lock:
            key_def = self._keys.get(name)
        if key_def is None:
            raise KeyError(f"context key {name!r} not registered")
        return key_def

    def is_registered(self, name: str) -> bool:
        with self._lock:
            return name in self._keys

    def all_keys(self) -> list[KeyDef]:
        with self._lock:
            return list(self._keys.values())


_global_key_registry = KeyRegistry()


def register_key(key_def: KeyDef) -> str:
    """Register a context key. Call at module level.

    Raises RuntimeError on duplicate registration.
    """
    return _global_key_registry.register(key_def)


def must_get_key(name: str) -> KeyDef:
    return _global_key_registry.must_get(name)


def is_registered(name: str) -> bool:
    return _global_key_registry.is_registered(name)


def all_keys() -> list[KeyDef]:
    return _global_key_registry.all_keys()


# --- Core keys (registered here, used by the engine) ---

KEY_NEEDS_RERUN: str = register_key(KeyDef(
    name="needs_rerun",
    description="Signal to retry the current turn",
    type="bool",
    category="core",
))

KEY_INTERNAL_QUERY: str = register_key(KeyDef(
    name="internal_query",
    description="Marks an LLM call as internal (not logged as user turn)",
    type="bool",
    category="core",
))

KEY_STRATEGY_OVERRIDE: str = register_key(KeyDef(
    name="strategy_override",
    description="User override for reasoning strategy",
    type="Strategy",
    category="core",
))

KEY_THINKING: str = register_key(KeyDef(
    name="thinking",
    description="ThinkingStream for the current turn",
    type="ThinkingStream",
    category="core",
))
