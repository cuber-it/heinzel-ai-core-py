"""Strategy, ThinkingStream, and backtracking support."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Callable

from core.keys import KEY_THINKING

if TYPE_CHECKING:
    from core.context import Context

__all__ = [
    "Strategy",
    "ThinkingStep",
    "Checkpoint",
    "ThinkingStream",
    "init_thinking",
    "get_thinking",
]


class Strategy(IntEnum):
    """Defines how the agent thinks."""

    PASSTHROUGH = 0       # Direct to LLM, no reasoning
    CHAIN_OF_THOUGHT = 1  # Agent-controlled multi-step
    DEEP_REASONING = 2    # Agent-controlled deep analysis
    REACT = 3             # Tool-using reasoning (Reason -> Act -> Observe)
    NATIVE = 4            # Delegate to model's native reasoning

    def __str__(self) -> str:
        return _STRATEGY_NAMES.get(self, "unknown")


_STRATEGY_NAMES: dict[Strategy, str] = {
    Strategy.PASSTHROUGH: "passthrough",
    Strategy.CHAIN_OF_THOUGHT: "chain_of_thought",
    Strategy.DEEP_REASONING: "deep_reasoning",
    Strategy.REACT: "react",
    Strategy.NATIVE: "native",
}


@dataclass
class ThinkingStep:
    """One step in the reasoning process -- streamed live."""

    step: int = 0
    type: str = ""       # classify, think, memory, tool, validate, backtrack, synthesize
    content: str = ""
    source: str = ""     # which addon/provider produced this
    time: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        return f"[{self.type}] {self.content}"


@dataclass
class Checkpoint:
    """Saves state for backtracking."""

    step: int = 0
    state: dict[str, Any] = field(default_factory=dict)
    message_count: int = 0
    alternatives: list[Strategy] = field(default_factory=list)


class ThinkingStream:
    """Collects steps and checkpoints."""

    def __init__(self, on_step: Callable[[ThinkingStep], None] | None = None) -> None:
        self.steps: list[ThinkingStep] = []
        self.checkpoints: list[Checkpoint] = []
        self.on_step = on_step

    def add_step(self, step_type: str, content: str, source: str) -> None:
        thinking_step = ThinkingStep(
            step=len(self.steps) + 1,
            type=step_type,
            content=content,
            source=source,
            time=datetime.now(),
        )
        self.steps.append(thinking_step)
        if self.on_step is not None:
            self.on_step(thinking_step)

    def save_checkpoint(self, ctx: Context, alternatives: list[Strategy]) -> None:
        """Create a backtracking point."""
        with ctx._lock:
            state_copy = dict(ctx.state)

        self.checkpoints.append(Checkpoint(
            step=len(self.steps),
            state=state_copy,
            message_count=len(ctx.messages),
            alternatives=list(alternatives),
        ))
        self.add_step("checkpoint", f"saved, {len(alternatives)} alternatives", "reasoning")

    def backtrack(self, ctx: Context) -> tuple[Strategy, bool]:
        """Restore the last checkpoint and return the next alternative.

        Returns (strategy, True) on success, (Strategy.PASSTHROUGH, False) if
        no checkpoints or no alternatives left.
        """
        if not self.checkpoints:
            return Strategy.PASSTHROUGH, False

        last = self.checkpoints[-1]

        if not last.alternatives:
            self.checkpoints.pop()
            self.add_step("backtrack", "no alternatives left, popping checkpoint", "reasoning")
            return self.backtrack(ctx)

        next_strategy = last.alternatives.pop(0)

        with ctx._lock:
            ctx.state = dict(last.state)
            if last.message_count < len(ctx.messages):
                ctx.messages = ctx.messages[:last.message_count]
            ctx.output = ""
            ctx.error = None
            ctx.halt = False

        self.add_step("backtrack", f"restored checkpoint, trying {next_strategy}", "reasoning")
        return next_strategy, True


def init_thinking(
    ctx: Context,
    on_step: Callable[[ThinkingStep], None] | None = None,
) -> ThinkingStream:
    """Set up the thinking stream on the context."""
    stream = ThinkingStream(on_step)
    ctx.set(KEY_THINKING, stream)
    return stream


def get_thinking(ctx: Context) -> ThinkingStream | None:
    """Retrieve the thinking stream from context."""
    value, ok = ctx.get(KEY_THINKING)
    if not ok:
        return None
    if not isinstance(value, ThinkingStream):
        return None
    return value
