"""Session -- lifecycle management for conversations.

Sessions have an ID, title, start/end time, and can be resumed.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from core.context import Message

__all__ = [
    "Session",
    "SessionManager",
]


@dataclass
class Session:
    """Represents a conversation with start, end, and metadata."""

    id: str = ""
    title: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None  # None = still active
    messages: int = 0  # message count at last save


def _generate_session_id() -> str:
    return os.urandom(8).hex()


class SessionManager:
    """Tracks active and historical sessions."""

    def __init__(
        self,
        on_save: Callable[[Session], None] | None = None,
        on_load: Callable[[str], list[Message]] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._active: Session | None = None
        self._history: list[Session] = []
        self._on_save = on_save
        self._on_load = on_load

    def start(self, title: str) -> Session:
        """Begin a new session. Ends the current one if active."""
        with self._lock:
            if self._active is not None:
                self._end_current()

            session = Session(
                id=_generate_session_id(),
                title=title,
                start_time=datetime.now(),
            )
            self._active = session
            return session

    def end(self) -> None:
        with self._lock:
            if self._active is not None:
                self._end_current()

    def _end_current(self) -> None:
        """Close active session (must hold lock)."""
        assert self._active is not None
        self._active.end_time = datetime.now()
        self._history.append(self._active)
        if self._on_save is not None:
            self._on_save(self._active)
        self._active = None

    def active(self) -> Session | None:
        with self._lock:
            return self._active

    def resume(self, session_id: str) -> tuple[Session | None, list[Message] | None]:
        """Restore a previous session by ID."""
        with self._lock:
            if self._active is not None:
                self._end_current()

            for index, session in enumerate(self._history):
                if session.id == session_id:
                    new_session = Session(
                        id=session.id,
                        title=session.title,
                        start_time=datetime.now(),
                    )
                    self._active = new_session
                    self._history.pop(index)

                    messages: list[Message] | None = None
                    if self._on_load is not None:
                        messages = self._on_load(session_id)
                    return new_session, messages

            return None, None

    def set_title(self, title: str) -> None:
        with self._lock:
            if self._active is not None:
                self._active.title = title

    def auto_title(self, first_message: str) -> None:
        """Generate a title from the first user message."""
        with self._lock:
            if self._active is not None and self._active.title == "":
                title = first_message
                if len(title) > 60:
                    title = title[:60] + "..."
                self._active.title = title

    def update_message_count(self, count: int) -> None:
        with self._lock:
            if self._active is not None:
                self._active.messages = count

    def list(self) -> list[Session]:
        with self._lock:
            result: list[Session] = []
            if self._active is not None:
                result.append(self._active)
            result.extend(self._history)
            return result

    def history(self) -> list[Session]:
        with self._lock:
            return list(self._history)

    def load_history(self, sessions: list[Session]) -> None:
        """Bulk-load historical sessions (e.g. from DB at startup)."""
        with self._lock:
            self._history = list(sessions)
