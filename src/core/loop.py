"""Loop -- the core cognitive loop: input, memory, context, LLM, tools, output."""

from __future__ import annotations

import concurrent.futures
import traceback
from typing import TYPE_CHECKING, Callable

from core.context import Context
from core.hooks import HookPoint
from core.keys import KEY_INTERNAL_QUERY, KEY_NEEDS_RERUN

if TYPE_CHECKING:
    from core.dispatcher import Dispatcher

__all__ = ["Loop"]


class Loop:
    """The core cognitive loop.

    It is intentionally simple -- all intelligence sits in the addons.
    """

    def __init__(self, dispatcher: Dispatcher) -> None:
        self.dispatcher = dispatcher
        self.max_turns: int = 100

    def run(self, ctx: Context, user_input: str) -> str:
        """Execute one complete turn: input -> process -> output.

        Recovers from exceptions -- a single turn crash never kills the agent.
        """
        try:
            return self._run_inner(ctx, user_input)
        except Exception as exc:
            ctx.output = f"Interner Fehler: {exc}"
            ctx.error = exc
            ctx.log.log_with_meta("error", f"PANIC: {exc}\n{traceback.format_exc()}", "loop", "panic")
            return ctx.output

    def _run_inner(self, ctx: Context, user_input: str) -> str:
        ctx.input = user_input
        ctx.output = ""
        ctx.halt = False
        ctx.error = None
        ctx.prompts.clear_turn()

        # Internal queries (triage, reasoning steps) -- fast path, only LLM call
        value, is_internal = ctx.get(KEY_INTERNAL_QUERY)
        if is_internal and isinstance(value, bool) and value:
            return self._run_internal(ctx, user_input)

        # Input phase
        ctx.add_message("user", user_input)
        self.dispatcher.dispatch(HookPoint.ON_INPUT, ctx)
        if ctx.halt:
            return ctx.output

        self.dispatcher.dispatch(HookPoint.ON_INPUT_PARSED, ctx)
        self.dispatcher.dispatch(HookPoint.ON_INPUT_CLASSIFIED, ctx)
        if ctx.halt:
            return ctx.output

        # Memory phase -- try System 1 first
        self.dispatcher.dispatch(HookPoint.ON_MEMORY_QUERY, ctx)
        if ctx.memory_results:
            self.dispatcher.dispatch(HookPoint.ON_MEMORY_HIT, ctx)
        else:
            self.dispatcher.dispatch(HookPoint.ON_MEMORY_MISS, ctx)
        if ctx.halt:
            return ctx.output

        # Context building -- addons inject prompt blocks, compose final prompt
        self.dispatcher.dispatch(HookPoint.ON_CONTEXT_BUILD, ctx)
        ctx.system_prompt = ctx.prompts.compose()

        # Check token budget
        if ctx.over_budget():
            self.dispatcher.dispatch(HookPoint.ON_CONTEXT_OVERFLOW, ctx)

        self.dispatcher.dispatch(HookPoint.ON_CONTEXT_READY, ctx)
        if ctx.halt:
            return ctx.output

        # LLM call (System 2) -- max 1 retry if addon requests it (prevent loops)
        for _llm_attempt in range(2):
            self.dispatcher.dispatch(HookPoint.ON_LLM_CALL, ctx)
            if ctx.error is not None:
                ctx.log.log_with_meta("error", str(ctx.error), "llm", "on_llm_error")
                self.dispatcher.dispatch(HookPoint.ON_LLM_ERROR, ctx)
                if ctx.halt:
                    return ctx.output
                self.dispatcher.dispatch(HookPoint.ON_LLM_FALLBACK, ctx)
            else:
                self.dispatcher.dispatch(HookPoint.ON_LLM_RESPONSE, ctx)

            # Check if any addon wants a re-run (e.g. web search fallback)
            value, ok = ctx.get(KEY_NEEDS_RERUN)
            if ok and value:
                ctx.set(KEY_NEEDS_RERUN, None)
                ctx.prompts.clear_turn()
                self.dispatcher.dispatch(HookPoint.ON_CONTEXT_BUILD, ctx)
                ctx.system_prompt = ctx.prompts.compose()
                continue
            break

        if ctx.halt:
            return ctx.output

        # Tool loop -- LLM may request tools, results go back to LLM
        turns = 0
        while ctx.tool_calls and turns < self.max_turns:
            turns += 1
            calls = ctx.tool_calls
            ctx.tool_calls = []

            # Execute tool calls in parallel
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = {}
                for index, call in enumerate(calls):
                    ctx.log.log_with_meta(
                        "tool", call.name, "mcp", "on_tool_request",
                        {"args": call.args},
                    )

                    def _dispatch_tool(idx: int = index) -> int:
                        self.dispatcher.dispatch(HookPoint.ON_TOOL_REQUEST, ctx)
                        return idx

                    futures[executor.submit(_dispatch_tool)] = index

                for future in concurrent.futures.as_completed(futures):
                    index = future.result()
                    if ctx.error is not None:
                        self.dispatcher.dispatch(HookPoint.ON_TOOL_ERROR, ctx)
                    else:
                        self.dispatcher.dispatch(HookPoint.ON_TOOL_RESPONSE, ctx)

            # Add all tool results as messages
            for call in calls:
                if call.result:
                    ctx.add_message("tool", call.result)

            if ctx.halt:
                return ctx.output

            # LLM continues with tool results
            ctx.output = ""
            self.dispatcher.dispatch(HookPoint.ON_LLM_CALL, ctx)
            if ctx.error is not None:
                self.dispatcher.dispatch(HookPoint.ON_LLM_ERROR, ctx)
            else:
                self.dispatcher.dispatch(HookPoint.ON_LLM_RESPONSE, ctx)

        # Output phase
        self.dispatcher.dispatch(HookPoint.ON_OUTPUT, ctx)
        self.dispatcher.dispatch(HookPoint.ON_OUTPUT_FORMATTED, ctx)

        if ctx.output:
            ctx.add_message("assistant", ctx.output)

        return ctx.output

    def _run_internal(self, ctx: Context, user_input: str) -> str:
        """Stripped-down loop for internal queries (triage, reasoning steps).

        No addon hooks except OnLLMCall -- avoids side effects,
        double-dispatch, and message pollution.
        """
        ctx.add_message("user", user_input)
        self.dispatcher.dispatch(HookPoint.ON_LLM_CALL, ctx)
        if ctx.error is not None:
            return ""
        return ctx.output

    def session(
        self,
        session_id: str,
        input_fn: Callable[[], tuple[str, bool]],
        output_fn: Callable[[str], None],
    ) -> None:
        """Run a complete session with the loop."""
        ctx = Context(session_id)

        self.dispatcher.dispatch(HookPoint.ON_SESSION_START, ctx)
        self.dispatcher.dispatch(HookPoint.ON_LOOP_START, ctx)

        try:
            while True:
                user_input, ok = input_fn()
                if not ok:
                    break

                output = self.run(ctx, user_input)
                if output:
                    output_fn(output)

                if ctx.halt:
                    self.dispatcher.dispatch(HookPoint.ON_LOOP_ABORT, ctx)
                    break
        finally:
            self.dispatcher.dispatch(HookPoint.ON_LOOP_END, ctx)
            self.dispatcher.dispatch(HookPoint.ON_SESSION_END, ctx)

    def __str__(self) -> str:
        addons = self.dispatcher.list_addons()
        return f"Loop: {len(addons)} addons, max {self.max_turns} turns"
