"""Tests for dispatcher module -- matches Go core/dispatcher_test.go."""

from core.addon import AddonType, BaseAddon, Command, Result
from core.context import Context
from core.dispatcher import Dispatcher
from core.hooks import HookPoint


class MockAddon(BaseAddon):
    """Test helper that records hook invocations."""

    def __init__(
        self,
        addon_name: str = "mock",
        addon_type: AddonType = AddonType.FILTER,
        addon_hooks: list[HookPoint] | None = None,
        handle_fn=None,
        addon_commands: list[Command] | None = None,
        start_err: Exception | None = None,
    ) -> None:
        self._name = addon_name
        self._type = addon_type
        self._hooks = addon_hooks or []
        self._handle_fn = handle_fn
        self._commands = addon_commands
        self._start_err = start_err
        self.handled: list[HookPoint] = []
        self.stopped = False

    def name(self) -> str:
        return self._name

    def type(self) -> AddonType:
        return self._type

    def hooks(self) -> list[HookPoint]:
        return self._hooks

    def handle(self, hook: HookPoint, ctx: Context) -> Result:
        self.handled.append(hook)
        if self._handle_fn is not None:
            return self._handle_fn(hook, ctx)
        return Result()

    def commands(self) -> list[Command] | None:
        return self._commands

    def handle_command(self, cmd: str, args: str, ctx: Context) -> str:
        return f"{self._name} handled {cmd}({args})"

    def start(self) -> None:
        if self._start_err is not None:
            raise self._start_err

    def stop(self) -> None:
        self.stopped = True


def test_register_addon():
    disp = Dispatcher()
    addon = MockAddon(addon_name="test-addon", addon_hooks=[HookPoint.ON_INPUT])

    disp.register(addon, 10)

    found, ok = disp.get_addon("test-addon")
    assert ok is True
    assert found is not None
    assert found.name() == "test-addon"


def test_register_duplicate():
    disp = Dispatcher()
    addon1 = MockAddon(addon_name="dup", addon_hooks=[HookPoint.ON_INPUT])
    addon2 = MockAddon(addon_name="dup", addon_hooks=[HookPoint.ON_OUTPUT])

    disp.register(addon1, 10)

    try:
        disp.register(addon2, 20)
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_dispatch_calls_handle_in_priority_order():
    disp = Dispatcher()
    order: list[str] = []

    addon_a = MockAddon(
        addon_name="alpha",
        addon_hooks=[HookPoint.ON_INPUT],
        handle_fn=lambda hook, ctx: (order.append("alpha"), Result())[1],
    )
    addon_b = MockAddon(
        addon_name="beta",
        addon_hooks=[HookPoint.ON_INPUT],
        handle_fn=lambda hook, ctx: (order.append("beta"), Result())[1],
    )

    # beta at priority 5 (earlier), alpha at priority 10 (later)
    disp.register(addon_b, 5)
    disp.register(addon_a, 10)

    ctx = Context("test")
    disp.dispatch(HookPoint.ON_INPUT, ctx)

    assert len(order) == 2
    assert order[0] == "beta"
    assert order[1] == "alpha"


def test_dispatch_multiple_addons_same_hook():
    disp = Dispatcher()

    addon1 = MockAddon(addon_name="first", addon_hooks=[HookPoint.ON_OUTPUT])
    addon2 = MockAddon(addon_name="second", addon_hooks=[HookPoint.ON_OUTPUT])
    addon3 = MockAddon(addon_name="third", addon_hooks=[HookPoint.ON_OUTPUT])

    disp.register(addon1, 30)
    disp.register(addon2, 10)
    disp.register(addon3, 20)

    ctx = Context("test")
    results = disp.dispatch(HookPoint.ON_OUTPUT, ctx)

    assert len(results) == 3
    assert len(addon1.handled) == 1
    assert len(addon2.handled) == 1
    assert len(addon3.handled) == 1


def test_dispatch_halt_stops_chain():
    disp = Dispatcher()

    addon_a = MockAddon(
        addon_name="halter",
        addon_hooks=[HookPoint.ON_INPUT],
        handle_fn=lambda hook, ctx: Result(halt=True),
    )
    addon_b = MockAddon(addon_name="after-halt", addon_hooks=[HookPoint.ON_INPUT])

    disp.register(addon_a, 10)
    disp.register(addon_b, 20)

    ctx = Context("test")
    results = disp.dispatch(HookPoint.ON_INPUT, ctx)

    assert ctx.halt is True
    assert len(results) == 1
    assert len(addon_b.handled) == 0


def test_dispatch_context_update():
    disp = Dispatcher()

    addon = MockAddon(
        addon_name="updater",
        addon_hooks=[HookPoint.ON_INPUT],
        handle_fn=lambda hook, ctx: Result(context_update={"injected": "value"}),
    )
    disp.register(addon, 10)

    ctx = Context("test")
    disp.dispatch(HookPoint.ON_INPUT, ctx)

    value, ok = ctx.get("injected")
    assert ok is True
    assert value == "value"


def test_dispatch_error_propagation():
    disp = Dispatcher()

    addon = MockAddon(
        addon_name="failer",
        addon_hooks=[HookPoint.ON_INPUT],
        handle_fn=lambda hook, ctx: Result(error=RuntimeError("something broke")),
    )
    disp.register(addon, 10)

    ctx = Context("test")
    disp.dispatch(HookPoint.ON_INPUT, ctx)

    assert ctx.error is not None
    assert str(ctx.error) == "something broke"


def test_list_addons():
    disp = Dispatcher()
    disp.register(MockAddon(addon_name="charlie", addon_hooks=[HookPoint.ON_INPUT]), 10)
    disp.register(MockAddon(addon_name="alpha", addon_hooks=[HookPoint.ON_INPUT]), 20)
    disp.register(MockAddon(addon_name="bravo", addon_hooks=[HookPoint.ON_INPUT]), 30)

    names = disp.list_addons()
    assert len(names) == 3
    # ListAddons sorts alphabetically
    assert names == ["alpha", "bravo", "charlie"]


def test_get_addon_not_found():
    disp = Dispatcher()
    _, ok = disp.get_addon("ghost")
    assert ok is False


def test_dispatch_command_routing():
    disp = Dispatcher()

    addon = MockAddon(
        addon_name="commander",
        addon_hooks=[HookPoint.ON_INPUT],
        addon_commands=[Command(name="test", description="test command")],
    )
    disp.register(addon, 10)

    ctx = Context("test")
    response, handled = disp.dispatch_command("test", "some args", ctx)

    assert handled is True
    assert response == "commander handled test(some args)"


def test_dispatch_command_unknown():
    disp = Dispatcher()

    addon = MockAddon(
        addon_name="commander",
        addon_hooks=[HookPoint.ON_INPUT],
        addon_commands=[Command(name="known", description="known command")],
    )
    disp.register(addon, 10)

    ctx = Context("test")
    response, handled = disp.dispatch_command("unknown", "", ctx)

    assert handled is False
    assert response == ""


def test_start_all_success():
    disp = Dispatcher()
    disp.register(MockAddon(addon_name="a", addon_hooks=[HookPoint.ON_INPUT]), 10)
    disp.register(MockAddon(addon_name="b", addon_hooks=[HookPoint.ON_INPUT]), 20)

    disp.start_all()  # should not raise


def test_start_all_failure():
    disp = Dispatcher()
    disp.register(
        MockAddon(
            addon_name="broken",
            addon_hooks=[HookPoint.ON_INPUT],
            start_err=RuntimeError("init failed"),
        ),
        10,
    )

    try:
        disp.start_all()
        assert False, "should have raised"
    except RuntimeError:
        pass


def test_stop_all():
    disp = Dispatcher()
    addon_a = MockAddon(addon_name="a", addon_hooks=[HookPoint.ON_INPUT])
    addon_b = MockAddon(addon_name="b", addon_hooks=[HookPoint.ON_INPUT])
    disp.register(addon_a, 10)
    disp.register(addon_b, 20)

    disp.stop_all()

    assert addon_a.stopped is True
    assert addon_b.stopped is True


def test_unregister():
    disp = Dispatcher()
    addon = MockAddon(
        addon_name="removable",
        addon_hooks=[HookPoint.ON_INPUT, HookPoint.ON_OUTPUT],
    )
    disp.register(addon, 10)

    disp.unregister("removable")

    _, ok = disp.get_addon("removable")
    assert ok is False
    assert len(disp.list_addons()) == 0

    # Should not be called on dispatch
    ctx = Context("test")
    results = disp.dispatch(HookPoint.ON_INPUT, ctx)
    assert len(results) == 0


def test_hook_subscribers():
    disp = Dispatcher()
    disp.register(
        MockAddon(addon_name="a", addon_hooks=[HookPoint.ON_INPUT, HookPoint.ON_OUTPUT]),
        10,
    )
    disp.register(
        MockAddon(addon_name="b", addon_hooks=[HookPoint.ON_INPUT]),
        20,
    )

    input_subs = disp.hook_subscribers(HookPoint.ON_INPUT)
    assert len(input_subs) == 2

    output_subs = disp.hook_subscribers(HookPoint.ON_OUTPUT)
    assert len(output_subs) == 1

    memory_subs = disp.hook_subscribers(HookPoint.ON_MEMORY_QUERY)
    assert len(memory_subs) == 0


def test_register_at():
    disp = Dispatcher()
    # Addon declares hooks [ON_INPUT] but we register it at ON_OUTPUT instead
    addon = MockAddon(addon_name="custom", addon_hooks=[HookPoint.ON_INPUT])

    disp.register_at(addon, 10, HookPoint.ON_OUTPUT, HookPoint.ON_LLM_CALL)

    output_subs = disp.hook_subscribers(HookPoint.ON_OUTPUT)
    assert len(output_subs) == 1

    llm_subs = disp.hook_subscribers(HookPoint.ON_LLM_CALL)
    assert len(llm_subs) == 1

    input_subs = disp.hook_subscribers(HookPoint.ON_INPUT)
    assert len(input_subs) == 0
