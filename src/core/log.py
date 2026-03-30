"""Logging -- minimal structured logging for headless operation."""

from __future__ import annotations

import sys
from datetime import datetime
from enum import IntEnum

__all__ = [
    "LogLevel",
    "Logger",
]


class LogLevel(IntEnum):
    """Log severity."""

    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3

    def __str__(self) -> str:
        return _LOG_LEVEL_NAMES.get(self, "UNKNOWN")


_LOG_LEVEL_NAMES: dict[LogLevel, str] = {
    LogLevel.DEBUG: "DEBUG",
    LogLevel.INFO: "INFO",
    LogLevel.WARN: "WARN",
    LogLevel.ERROR: "ERROR",
}


class Logger:
    """Writes structured log lines to stderr."""

    def __init__(self, name: str, min_level: LogLevel = LogLevel.INFO) -> None:
        self.name = name
        self.min_level = min_level

    def log(self, level: LogLevel, fmt: str, *args: object) -> None:
        if level < self.min_level:
            return
        message = fmt % args if args else fmt
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.name} {level}: {message}", file=sys.stderr)

    def debug(self, fmt: str, *args: object) -> None:
        self.log(LogLevel.DEBUG, fmt, *args)

    def info(self, fmt: str, *args: object) -> None:
        self.log(LogLevel.INFO, fmt, *args)

    def warn(self, fmt: str, *args: object) -> None:
        self.log(LogLevel.WARN, fmt, *args)

    def error(self, fmt: str, *args: object) -> None:
        self.log(LogLevel.ERROR, fmt, *args)
