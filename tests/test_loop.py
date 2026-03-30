"""Tests for loop module -- matches Go core/loop_test.go."""

from core.addon import AddonType, BaseAddon, Result
from core.context import Context, ToolCall
from core.dispatcher import Dispatcher
from core.hooks import HookPoint
from core.keys import KEY_INTERNAL_QUERY, KEY_NEEDS_RERUN
from core.loop import Loop


class MockProvider(BaseAddon):
    """Simulates an LLM provider addon."""

    def __init__(self, response: str = "", error_on: int = 0) -> None:
        self._response = response
        self._error_on = error_on
        self.call_count = 0

    def name(self) -> str:
        return "mock-provider"

    def type(self) -> AddonType:
        return AddonType.PROVIDER

    def hooks(self) -> list[HookPoint]:
        return [HookPoint.ON_LLM_CALL]

    def handle(self, hook: HookPoint, ctx: Context) -> Result:
        self.call_count += 1
        if self._error_on > 0 and self.call_count == self._error_on:
            error = RuntimeError(f"LLM error on call {self.call_count}")
            ctx.error = error
            return Result(error=error)
        ctx.output = self._response
        return Result()

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class MockAddon(BaseAddon):
    """Generic test addon."""

    def __init__(
        self,
        addon_name: str = "mock",
        addon_hooks: list[HookPoint] | None = None,
        handle_fn=None,
    ) -> None:
        self._name = addon_name
        self._hooks = addon_hooks or []
        self._handle_fn = handle_fn

    def name(self) -> str:
        return self._name

    def type(self) -> AddonType:
        return AddonType.FILTER

    def hooks(self) -> list[HookPoint]:
        return self._hooks

    def handle(self, hook: HookPoint, ctx: Context) -> Result:
        if self._handle_fn is not None:
            return self._handle_fn(hook, ctx)
        return Result()

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def test_loop_simple_input_output():
    disp = Dispatcher()
    provider = MockProvider(response="hello back")
    disp.register(provider, 100)

    loop = Loop(disp)
    ctx = Context("test")

    output = loop.run(ctx, "hello")
    assert output == "hello back"
    assert ctx.input == "hello"


def test_loop_halt_stops_processing():
    disp = Dispatcher()

    def halt_handler(hook, ctx):
        ctx.output = "halted early"
        return Result(halt=True)

    halter = MockAddon(
        addon_name="halter",
        addon_hooks=[HookPoint.ON_INPUT],
        handle_fn=halt_handler,
    )
    disp.register(halter, 10)

    provider = MockProvider(response="should not appear")
    disp.register(provider, 100)

    loop = Loop(disp)
    ctx = Context("test")

    output = loop.run(ctx, "test")
    assert output == "halted early"
    assert provider.call_count == 0


def test_loop_llm_error_triggers_on_llm_error():
    disp = Dispatcher()

    provider = MockProvider(response="ok", error_on=1)
    disp.register(provider, 100)

    error_handled = [False]

    def error_handler(hook, ctx):
        error_handled[0] = True
        ctx.output = "error handled gracefully"
        return Result()

    handler = MockAddon(
        addon_name="error-handler",
        addon_hooks=[HookPoint.ON_LLM_ERROR],
        handle_fn=error_handler,
    )
    disp.register(handler, 50)

    loop = Loop(disp)
    ctx = Context("test")

    loop.run(ctx, "test")

    assert error_handled[0] is True
    assert ctx.error is not None


def test_loop_tool_calls_get_executed():
    disp = Dispatcher()

    call_sequence = [0]

    def provider_handler(hook, ctx):
        call_sequence[0] += 1
        if call_sequence[0] == 1:
            ctx.tool_calls = [
                ToolCall(id="tc1", name="calculator", args={"expr": "2+2"}),
            ]
            ctx.output = ""
        else:
            ctx.output = "the answer is 4"
            ctx.tool_calls = []
        return Result()

    provider = MockAddon(
        addon_name="tool-provider",
        addon_hooks=[HookPoint.ON_LLM_CALL],
        handle_fn=provider_handler,
    )
    disp.register(provider, 100)

    tool_executor = MockAddon(
        addon_name="tool-executor",
        addon_hooks=[HookPoint.ON_TOOL_REQUEST],
    )
    disp.register(tool_executor, 50)

    loop = Loop(disp)
    ctx = Context("test")

    output = loop.run(ctx, "what is 2+2?")
    assert output == "the answer is 4"
    assert call_sequence[0] >= 2


def test_loop_needs_rerun_causes_retry():
    disp = Dispatcher()

    llm_calls = [0]

    def provider_handler(hook, ctx):
        llm_calls[0] += 1
        ctx.output = f"attempt {llm_calls[0]}"
        return Result()

    provider = MockAddon(
        addon_name="rerun-provider",
        addon_hooks=[HookPoint.ON_LLM_CALL],
        handle_fn=provider_handler,
    )
    disp.register(provider, 100)

    rerun_requested = [False]

    def rerun_handler(hook, ctx):
        if not rerun_requested[0]:
            rerun_requested[0] = True
            ctx.set(KEY_NEEDS_RERUN, True)
        return Result()

    rerunner = MockAddon(
        addon_name="rerunner",
        addon_hooks=[HookPoint.ON_LLM_RESPONSE],
        handle_fn=rerun_handler,
    )
    disp.register(rerunner, 50)

    loop = Loop(disp)
    ctx = Context("test")

    output = loop.run(ctx, "test rerun")
    assert llm_calls[0] >= 2
    assert output == "attempt 2"


def test_loop_panic_recovery():
    disp = Dispatcher()

    def panic_handler(hook, ctx):
        raise RuntimeError("addon exploded")

    panicker = MockAddon(
        addon_name="panicker",
        addon_hooks=[HookPoint.ON_INPUT],
        handle_fn=panic_handler,
    )
    disp.register(panicker, 10)

    loop = Loop(disp)
    ctx = Context("test")

    # Should not crash
    loop.run(ctx, "trigger panic")

    assert "Interner Fehler" in ctx.output
    assert ctx.error is not None


def test_loop_max_turns():
    disp = Dispatcher()

    def infinite_handler(hook, ctx):
        ctx.tool_calls = [ToolCall(id="tc", name="loop-tool")]
        return Result()

    provider = MockAddon(
        addon_name="infinite-tools",
        addon_hooks=[HookPoint.ON_LLM_CALL],
        handle_fn=infinite_handler,
    )
    disp.register(provider, 100)

    loop = Loop(disp)
    loop.max_turns = 3

    ctx = Context("test")
    loop.run(ctx, "infinite loop test")
    # Should terminate without hanging -- if we get here, max_turns worked


def test_loop_string():
    disp = Dispatcher()
    disp.register(MockAddon(addon_name="a", addon_hooks=[HookPoint.ON_INPUT]), 10)
    disp.register(MockAddon(addon_name="b", addon_hooks=[HookPoint.ON_INPUT]), 20)

    loop = Loop(disp)
    summary = str(loop)

    assert "2 addons" in summary


def test_loop_session():
    disp = Dispatcher()
    provider = MockProvider(response="session reply")
    disp.register(provider, 100)

    loop = Loop(disp)

    inputs = ["hello", "world"]
    input_idx = [0]
    outputs: list[str] = []

    def input_fn():
        if input_idx[0] >= len(inputs):
            return "", False
        val = inputs[input_idx[0]]
        input_idx[0] += 1
        return val, True

    def output_fn(output: str):
        outputs.append(output)

    loop.session("test-session", input_fn, output_fn)

    assert len(outputs) == 2
    for out in outputs:
        assert out == "session reply"


def test_loop_internal_query_fast_path():
    """Internal queries should only dispatch ON_LLM_CALL, skipping all other hooks."""
    disp = Dispatcher()

    input_called = [False]

    def input_handler(hook, ctx):
        input_called[0] = True
        return Result()

    input_addon = MockAddon(
        addon_name="input-tracker",
        addon_hooks=[HookPoint.ON_INPUT],
        handle_fn=input_handler,
    )
    disp.register(input_addon, 10)

    provider = MockProvider(response="internal response")
    disp.register(provider, 100)

    loop = Loop(disp)
    ctx = Context("test")
    ctx.set(KEY_INTERNAL_QUERY, True)

    output = loop.run(ctx, "internal query")
    assert output == "internal response"
    # ON_INPUT should NOT have been called for internal queries
    assert input_called[0] is False
