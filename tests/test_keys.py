"""Tests for keys module."""

import pytest

from core.keys import (
    KEY_INTERNAL_QUERY,
    KEY_NEEDS_RERUN,
    KEY_STRATEGY_OVERRIDE,
    KEY_THINKING,
    KeyDef,
    KeyRegistry,
    all_keys,
    is_registered,
    must_get_key,
)


def test_core_keys_registered():
    """All core keys should be registered at module load time."""
    assert is_registered("needs_rerun")
    assert is_registered("internal_query")
    assert is_registered("strategy_override")
    assert is_registered("thinking")


def test_key_constants_are_strings():
    assert KEY_NEEDS_RERUN == "needs_rerun"
    assert KEY_INTERNAL_QUERY == "internal_query"
    assert KEY_STRATEGY_OVERRIDE == "strategy_override"
    assert KEY_THINKING == "thinking"


def test_must_get_key_exists():
    key_def = must_get_key("needs_rerun")
    assert key_def.name == "needs_rerun"
    assert key_def.category == "core"
    assert key_def.type == "bool"


def test_must_get_key_missing():
    with pytest.raises(KeyError):
        must_get_key("nonexistent_key")


def test_all_keys_returns_list():
    keys = all_keys()
    assert isinstance(keys, list)
    assert len(keys) >= 4  # at least the 4 core keys
    names = {key_def.name for key_def in keys}
    assert "needs_rerun" in names
    assert "internal_query" in names
    assert "strategy_override" in names
    assert "thinking" in names


def test_registry_duplicate_raises():
    registry = KeyRegistry()
    registry.register(KeyDef(name="test_dup", description="test", type="str", category="test"))
    with pytest.raises(RuntimeError):
        registry.register(KeyDef(name="test_dup", description="test2", type="str", category="test"))


def test_registry_is_registered():
    registry = KeyRegistry()
    assert not registry.is_registered("foo")
    registry.register(KeyDef(name="foo", description="test", type="str", category="test"))
    assert registry.is_registered("foo")
