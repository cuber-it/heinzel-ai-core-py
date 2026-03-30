"""Tests for context module -- matches Go core/context_test.go."""

from core.context import Context
from core.prompt import PromptLayer


def test_new_context():
    ctx = Context("test")

    assert ctx.session_id != ""
    assert ctx.session_id.startswith("test-")
    assert ctx.start_time is not None
    assert ctx.state is not None
    assert isinstance(ctx.state, dict)
    assert ctx.memory_results is not None
    assert isinstance(ctx.memory_results, dict)
    assert ctx.prompts is not None
    assert ctx.log is not None
    assert ctx.token_budget == 200_000
    assert ctx.halt is False
    assert ctx.error is None


def test_set_get_string():
    ctx = Context("test")
    ctx.set("greeting", "hello")

    value, ok = ctx.get("greeting")
    assert ok is True
    assert value == "hello"


def test_set_get_int():
    ctx = Context("test")
    ctx.set("count", 42)

    value, ok = ctx.get("count")
    assert ok is True
    assert value == 42


def test_set_get_bool():
    ctx = Context("test")
    ctx.set("flag", True)

    value, ok = ctx.get("flag")
    assert ok is True
    assert value is True


def test_set_get_custom_type():
    class MyType:
        def __init__(self, val: int) -> None:
            self.val = val

    ctx = Context("test")
    obj = MyType(42)
    ctx.set("custom_key", obj)

    value, ok = ctx.get("custom_key")
    assert ok is True
    assert isinstance(value, MyType)
    assert value.val == 42


def test_set_get_none():
    ctx = Context("test")
    ctx.set("empty", None)

    value, ok = ctx.get("empty")
    assert ok is True
    assert value is None


def test_get_missing_key():
    ctx = Context("test")

    value, ok = ctx.get("nonexistent")
    assert ok is False
    assert value is None


def test_add_message():
    ctx = Context("test")

    ctx.add_message("user", "hello")
    ctx.add_message("assistant", "hi there")

    assert len(ctx.messages) == 2
    assert ctx.messages[0].role == "user"
    assert ctx.messages[0].content == "hello"
    assert ctx.messages[1].role == "assistant"
    assert ctx.messages[1].content == "hi there"
    assert ctx.messages[0].time is not None


def test_add_message_log_sync():
    ctx = Context("test")
    ctx.add_message("user", "test input")

    assert ctx.log.count() == 1


def test_messages_ordering():
    ctx = Context("test")
    contents = ["first", "second", "third", "fourth"]

    for index, content in enumerate(contents):
        role = "user" if index % 2 == 0 else "assistant"
        ctx.add_message(role, content)

    assert len(ctx.messages) == 4
    for index, expected in enumerate(contents):
        assert ctx.messages[index].content == expected


def test_token_estimate():
    ctx = Context("test")
    # 400 chars -> ~100 tokens
    content = "a" * 400
    ctx.add_message("user", content)

    estimate = ctx.token_estimate()
    assert 90 <= estimate <= 110


def test_token_estimate_includes_prompt():
    ctx = Context("test")
    ctx.prompts.set(PromptLayer.SYSTEM, "core", "x" * 800, 0)

    estimate = ctx.token_estimate()
    # 800 chars / 4 = 200 tokens from prompt alone
    assert estimate >= 190


def test_over_budget_false_when_unlimited():
    ctx = Context("test")
    ctx.token_budget = 0

    ctx.add_message("user", "x" * 100_000)
    assert ctx.over_budget() is False


def test_over_budget_false_under_budget():
    ctx = Context("test")
    ctx.token_budget = 1000

    ctx.add_message("user", "short message")
    assert ctx.over_budget() is False


def test_over_budget_true_when_exceeded():
    ctx = Context("test")
    ctx.token_budget = 10  # very tight budget

    ctx.add_message("user", "x" * 200)
    assert ctx.over_budget() is True


def test_over_budget_negative_budget():
    ctx = Context("test")
    ctx.token_budget = -1

    ctx.add_message("user", "x" * 100_000)
    assert ctx.over_budget() is False
