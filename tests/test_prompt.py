"""Tests for prompt module -- matches Go core/prompt_test.go."""

from core.prompt import PromptLayer, PromptManager


def test_prompt_set_and_compose_single_layer():
    pm = PromptManager()
    pm.set(PromptLayer.SYSTEM, "core", "You are a helpful agent.")

    result = pm.compose()
    assert result == "You are a helpful agent."


def test_prompt_multiple_layers_compose_in_order():
    pm = PromptManager()
    pm.set(PromptLayer.TURN, "memory", "Context: user likes Go")
    pm.set(PromptLayer.SYSTEM, "core", "System identity")
    pm.set(PromptLayer.USER, "prefs", "User preferences")
    pm.set(PromptLayer.SESSION, "session", "Session goals")

    result = pm.compose()
    parts = result.split("\n\n")

    assert len(parts) == 4
    # Order should be: System, Session, User, Turn
    assert parts[0] == "System identity"
    assert parts[1] == "Session goals"
    assert parts[2] == "User preferences"
    assert parts[3] == "Context: user likes Go"


def test_prompt_priority_within_layer():
    pm = PromptManager()
    pm.add(PromptLayer.SYSTEM, "secondary", "Secondary rule", 20)
    pm.add(PromptLayer.SYSTEM, "primary", "Primary rule", 10)
    pm.add(PromptLayer.SYSTEM, "tertiary", "Tertiary rule", 30)

    result = pm.compose()
    parts = result.split("\n\n")

    assert len(parts) == 3
    assert parts[0] == "Primary rule"
    assert parts[1] == "Secondary rule"
    assert parts[2] == "Tertiary rule"


def test_prompt_clear_turn():
    pm = PromptManager()
    pm.set(PromptLayer.SYSTEM, "core", "System prompt")
    pm.set(PromptLayer.TURN, "memory", "Turn-specific context")
    pm.set(PromptLayer.TURN, "tools", "Tool results", 10)

    pm.clear_turn()

    result = pm.compose()
    assert "Turn-specific" not in result
    assert "Tool results" not in result
    assert "System prompt" in result


def test_prompt_clear_turn_preserves_other_layers():
    pm = PromptManager()
    pm.set(PromptLayer.SYSTEM, "core", "System")
    pm.set(PromptLayer.SESSION, "sess", "Session")
    pm.set(PromptLayer.USER, "user", "User")
    pm.set(PromptLayer.TURN, "turn", "Turn")

    pm.clear_turn()
    blocks = pm.blocks()

    assert len(blocks) == 3


def test_prompt_blocks():
    pm = PromptManager()
    pm.set(PromptLayer.SYSTEM, "a", "content a", 10)
    pm.add(PromptLayer.TURN, "b", "content b", 20)

    blocks = pm.blocks()
    assert len(blocks) == 2

    found = any(
        block.source == "a"
        and block.layer == PromptLayer.SYSTEM
        and block.priority == 10
        for block in blocks
    )
    assert found


def test_prompt_empty_compose():
    pm = PromptManager()
    result = pm.compose()
    assert result == ""


def test_prompt_set_replaces_existing():
    pm = PromptManager()
    pm.set(PromptLayer.SYSTEM, "core", "version 1")
    pm.set(PromptLayer.SYSTEM, "core", "version 2")

    result = pm.compose()
    assert result == "version 2"
    assert len(pm.blocks()) == 1


def test_prompt_add_does_not_replace():
    pm = PromptManager()
    pm.add(PromptLayer.SYSTEM, "core", "version 1")
    pm.add(PromptLayer.SYSTEM, "core", "version 2")

    assert len(pm.blocks()) == 2


def test_prompt_empty_content_skipped():
    pm = PromptManager()
    pm.set(PromptLayer.SYSTEM, "core", "visible")
    pm.set(PromptLayer.SYSTEM, "empty", "", 10)

    result = pm.compose()
    assert result == "visible"


def test_prompt_clear_layer():
    pm = PromptManager()
    pm.set(PromptLayer.SYSTEM, "core", "system")
    pm.set(PromptLayer.SESSION, "sess", "session")

    pm.clear_layer(PromptLayer.SESSION)

    blocks = pm.blocks()
    assert len(blocks) == 1
    assert blocks[0].layer == PromptLayer.SYSTEM


def test_prompt_layer_string():
    tests = [
        (PromptLayer.SYSTEM, "system"),
        (PromptLayer.SESSION, "session"),
        (PromptLayer.USER, "user"),
        (PromptLayer.TURN, "turn"),
    ]
    for layer, expected in tests:
        assert str(layer) == expected
