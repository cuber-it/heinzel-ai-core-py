"""Context -- mutable pipeline state passed through every hook."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from core.prompt import ChatLog, PromptManager

__all__ = [
    "Message",
    "ToolCall",
    "Context",
]


@dataclass
class Message:
    """Represents one turn in the conversation."""

    role: str = ""       # "user", "assistant", "system", "tool"
    content: str = ""
    name: str = ""       # tool name if role=tool
    meta: dict[str, str] = field(default_factory=dict)
    time: datetime = field(default_factory=datetime.now)


@dataclass
class ToolCall:
    """Represents an LLM request to use a tool."""

    id: str = ""
    name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    result: str = ""


def _generate_id(prefix: str) -> str:
    random_bytes = os.urandom(4)
    return f"{prefix}-{random_bytes.hex()}"


class Context:
    """Mutable state passed through the pipeline. Any addon can read and modify it."""

    def __init__(self, prefix: str = "session") -> None:
        self._lock = threading.RWLock() if hasattr(threading, "RWLock") else threading.Lock()

        # Session
        self.session_id: str = _generate_id(prefix)
        self.start_time: datetime = datetime.now()

        # Conversation
        self.messages: list[Message] = []
        self.input: str = ""
        self.output: str = ""

        # Memory results from addons
        self.memory_results: dict[str, Any] = {}

        # LLM
        self.system_prompt: str = ""
        self.provider: str = ""
        self.model: str = ""

        # Prompt composition -- addons inject blocks per layer
        self.prompts: PromptManager = PromptManager()

        # Complete conversation log -- everything including internals
        self.log: ChatLog = ChatLog(self.session_id)

        # Token budget
        self.token_budget: int = 200_000

        # Tool calls
        self.tool_calls: list[ToolCall] = []

        # Arbitrary key-value store for addon communication
        self.state: dict[str, Any] = {}

        # Streaming -- callback for token-by-token output
        self.on_token: Callable[[str], None] | None = None

        # Signals
        self.halt: bool = False
        self.error: Exception | None = None

    def get(self, key: str) -> tuple[Any, bool]:
        with self._lock:
            if key in self.state:
                return self.state[key], True
            return None, False

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self.state[key] = value

    def add_message(self, role: str, content: str) -> None:
        with self._lock:
            self.messages.append(Message(
                role=role,
                content=content,
                time=datetime.now(),
            ))
        self.log.log(role, content, "")

    def token_estimate(self) -> int:
        total = len(self.prompts.compose()) // 4
        for message in self.messages:
            total += len(message.content) // 4
        return total

    def over_budget(self) -> bool:
        if self.token_budget <= 0:
            return False
        return self.token_estimate() > self.token_budget
