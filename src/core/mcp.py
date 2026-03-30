"""Tool and ToolRegistry for MCP tool management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Tool",
    "ToolRegistry",
]


@dataclass
class Tool:
    """Represents an MCP tool that the LLM can call."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """Holds all available tools from all MCP servers."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._sources: dict[str, str] = {}

    def register(self, tool: Tool, source: str) -> None:
        self._tools[tool.name] = tool
        self._sources[tool.name] = source

    def get(self, name: str) -> tuple[Tool, bool]:
        tool = self._tools.get(name)
        if tool is None:
            return Tool(), False
        return tool, True

    def source(self, name: str) -> str:
        return self._sources.get(name, "")

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def count(self) -> int:
        return len(self._tools)
