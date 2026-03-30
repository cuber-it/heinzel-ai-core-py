"""PromptManager -- 4-layer prompt composition (System, Session, User, Turn)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Any

__all__ = [
    "PromptLayer",
    "PromptBlock",
    "PromptManager",
    "ChatEntry",
    "ChatLog",
]


class PromptLayer(IntEnum):
    """Defines the hierarchy of prompt components."""

    SYSTEM = 0   # Agent identity, rules, capabilities -- persistent
    SESSION = 1  # Session-specific context, goals -- per session
    USER = 2     # User preferences, history summary -- per user
    TURN = 3     # Dynamic per-turn: tool results, memory, addon injections

    def __str__(self) -> str:
        return _LAYER_NAMES.get(self, "unknown")


_LAYER_NAMES: dict[PromptLayer, str] = {
    PromptLayer.SYSTEM: "system",
    PromptLayer.SESSION: "session",
    PromptLayer.USER: "user",
    PromptLayer.TURN: "turn",
}


@dataclass
class PromptBlock:
    """One piece of a composed prompt."""

    layer: PromptLayer
    source: str
    content: str
    priority: int = 0


class PromptManager:
    """Composes the final system prompt from layers."""

    def __init__(self) -> None:
        self._blocks: list[PromptBlock] = []

    def set(self, layer: PromptLayer, source: str, content: str, priority: int = 0) -> None:
        """Replace all blocks for a layer from a specific source."""
        self._blocks = [
            block for block in self._blocks
            if not (block.layer == layer and block.source == source)
        ]
        self._blocks.append(PromptBlock(
            layer=layer,
            source=source,
            content=content,
            priority=priority,
        ))

    def add(self, layer: PromptLayer, source: str, content: str, priority: int = 0) -> None:
        """Append a block without removing existing ones."""
        self._blocks.append(PromptBlock(
            layer=layer,
            source=source,
            content=content,
            priority=priority,
        ))

    def clear_layer(self, layer: PromptLayer) -> None:
        self._blocks = [block for block in self._blocks if block.layer != layer]

    def clear_turn(self) -> None:
        self.clear_layer(PromptLayer.TURN)

    def compose(self) -> str:
        """Build the final system prompt from all layers.

        Order: System -> Session -> User -> Turn, within each layer by priority.
        """
        sorted_blocks = sorted(self._blocks, key=lambda block: (block.layer, block.priority))
        parts = [block.content for block in sorted_blocks if block.content]
        return "\n\n".join(parts)

    def blocks(self) -> list[PromptBlock]:
        return list(self._blocks)


# === Chat Log ===


@dataclass
class ChatEntry:
    """One entry in the complete conversation log."""

    time: datetime = field(default_factory=datetime.now)
    role: str = ""        # user, assistant, system, tool, thinking, addon
    content: str = ""
    source: str = ""      # addon name, provider name
    hook: str = ""        # which hook triggered this
    tokens_in: int = 0
    tokens_out: int = 0
    latency: timedelta = field(default_factory=timedelta)
    meta: dict[str, Any] | None = None


class ChatLog:
    """Records the complete conversation including internal events."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.start_time = datetime.now()
        self.entries: list[ChatEntry] = []

    def log(self, role: str, content: str, source: str = "") -> None:
        self.entries.append(ChatEntry(
            time=datetime.now(),
            role=role,
            content=content,
            source=source,
        ))

    def log_with_meta(
        self,
        role: str,
        content: str,
        source: str,
        hook: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.entries.append(ChatEntry(
            time=datetime.now(),
            role=role,
            content=content,
            source=source,
            hook=hook,
            meta=meta,
        ))

    def log_llm(
        self,
        content: str,
        provider: str,
        tokens_in: int,
        tokens_out: int,
        latency: timedelta,
    ) -> None:
        """Add an LLM call entry with token counts and latency."""
        self.entries.append(ChatEntry(
            time=datetime.now(),
            role="assistant",
            content=content,
            source=provider,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency=latency,
        ))

    def count(self) -> int:
        return len(self.entries)

    def tokens_total(self) -> tuple[int, int]:
        """Return total tokens used as (total_in, total_out)."""
        total_in = sum(entry.tokens_in for entry in self.entries)
        total_out = sum(entry.tokens_out for entry in self.entries)
        return total_in, total_out
