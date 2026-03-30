"""HookPoints -- the 24 events in the cognitive loop."""

from enum import IntEnum

__all__ = ["HookPoint", "HOOK_COUNT"]


class HookPoint(IntEnum):
    """Defines when in the loop an addon gets called."""

    ON_SESSION_START = 0
    ON_SESSION_END = 1
    ON_INPUT = 2
    ON_INPUT_PARSED = 3
    ON_INPUT_CLASSIFIED = 4
    ON_MEMORY_QUERY = 5
    ON_MEMORY_HIT = 6
    ON_MEMORY_MISS = 7
    ON_CONTEXT_BUILD = 8
    ON_CONTEXT_READY = 9
    ON_CONTEXT_OVERFLOW = 10
    ON_LLM_CALL = 11
    ON_LLM_RESPONSE = 12
    ON_LLM_ERROR = 13
    ON_LLM_FALLBACK = 14
    ON_TOOL_REQUEST = 15
    ON_TOOL_RESPONSE = 16
    ON_TOOL_ERROR = 17
    ON_OUTPUT = 18
    ON_OUTPUT_FORMATTED = 19
    ON_LOOP_START = 20
    ON_LOOP_END = 21
    ON_LOOP_ABORT = 22
    ON_TICK = 23

    def __str__(self) -> str:
        return _HOOK_NAMES.get(self, "unknown")


HOOK_COUNT: int = 24

_HOOK_NAMES: dict[HookPoint, str] = {
    HookPoint.ON_SESSION_START: "on_session_start",
    HookPoint.ON_SESSION_END: "on_session_end",
    HookPoint.ON_INPUT: "on_input",
    HookPoint.ON_INPUT_PARSED: "on_input_parsed",
    HookPoint.ON_INPUT_CLASSIFIED: "on_input_classified",
    HookPoint.ON_MEMORY_QUERY: "on_memory_query",
    HookPoint.ON_MEMORY_HIT: "on_memory_hit",
    HookPoint.ON_MEMORY_MISS: "on_memory_miss",
    HookPoint.ON_CONTEXT_BUILD: "on_context_build",
    HookPoint.ON_CONTEXT_READY: "on_context_ready",
    HookPoint.ON_CONTEXT_OVERFLOW: "on_context_overflow",
    HookPoint.ON_LLM_CALL: "on_llm_call",
    HookPoint.ON_LLM_RESPONSE: "on_llm_response",
    HookPoint.ON_LLM_ERROR: "on_llm_error",
    HookPoint.ON_LLM_FALLBACK: "on_llm_fallback",
    HookPoint.ON_TOOL_REQUEST: "on_tool_request",
    HookPoint.ON_TOOL_RESPONSE: "on_tool_response",
    HookPoint.ON_TOOL_ERROR: "on_tool_error",
    HookPoint.ON_OUTPUT: "on_output",
    HookPoint.ON_OUTPUT_FORMATTED: "on_output_formatted",
    HookPoint.ON_LOOP_START: "on_loop_start",
    HookPoint.ON_LOOP_END: "on_loop_end",
    HookPoint.ON_LOOP_ABORT: "on_loop_abort",
    HookPoint.ON_TICK: "on_tick",
}
