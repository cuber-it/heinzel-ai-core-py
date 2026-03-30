"""HeartbeatAddon -- proactive agent behavior.

Fires periodically, checks tasks, acts autonomously.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.addon import AddonType, BaseAddon, Command, Result
from core.context import Context
from core.hooks import HookPoint
from core.keys import KEY_INTERNAL_QUERY, KEY_STRATEGY_OVERRIDE
from core.reasoning import Strategy, init_thinking

if TYPE_CHECKING:
    from core.loop import Loop

__all__ = ["HeartbeatAddon", "HeartbeatConfig"]

_DEFAULT_HEARTBEAT_INTERVAL = timedelta(minutes=30)
_HEARTBEAT_OK = "HEARTBEAT_OK"


class HeartbeatConfig:
    """Heartbeat settings."""

    def __init__(
        self,
        interval: timedelta = _DEFAULT_HEARTBEAT_INTERVAL,
        file_path: str = "",
        on_action: Callable[[str], None] | None = None,
    ) -> None:
        self.interval = interval
        self.file_path = file_path
        self.on_action = on_action


class HeartbeatAddon(BaseAddon):
    """Gives the agent a pulse -- wakes up periodically,
    checks a task file, and acts if something needs attention.
    """

    def __init__(self, config: HeartbeatConfig) -> None:
        self._interval = config.interval if config.interval else _DEFAULT_HEARTBEAT_INTERVAL
        self._file_path = config.file_path
        self._on_action = config.on_action
        self._loop: Loop | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False
        self._last_beat: datetime | None = None
        self._last_result: str = ""
        self._beat_count: int = 0

    def set_loop(self, loop: Loop) -> None:
        self._loop = loop

    def set_on_action(self, callback: Callable[[str], None]) -> None:
        self._on_action = callback

    def name(self) -> str:
        return "heartbeat"

    def type(self) -> AddonType:
        return AddonType.FILTER

    def hooks(self) -> list[HookPoint]:
        return [HookPoint.ON_SESSION_START]

    def start(self) -> None:
        pass

    def stop(self) -> None:
        with self._lock:
            if self._running:
                self._stop_event.set()
                self._running = False

    def handle(self, hook: HookPoint, ctx: Context) -> Result:
        if hook == HookPoint.ON_SESSION_START:
            self._start_pulse()
        return Result()

    def commands(self) -> list[Command]:
        return [
            Command(
                name="heartbeat",
                description="heartbeat control",
                usage="heartbeat [status|trigger|interval <duration>|edit]",
            ),
        ]

    def handle_command(self, cmd: str, args: str, ctx: Context) -> str:
        parts = args.split()
        sub = parts[0] if parts else ""

        if sub in ("", "status"):
            with self._lock:
                last_beat = "never"
                if self._last_beat is not None:
                    elapsed = datetime.now() - self._last_beat
                    last_beat = f"{elapsed.total_seconds():.0f}s ago"
                last_result = self._last_result or "(none)"
                if len(last_result) > 100:
                    last_result = last_result[:100] + "..."
                return (
                    f"Heartbeat: {self._running}\n"
                    f"Interval: {self._interval}\n"
                    f"File: {self._file_path}\n"
                    f"Beats: {self._beat_count}\n"
                    f"Last: {last_beat}\n"
                    f"Result: {last_result}"
                )

        if sub == "trigger":
            threading.Thread(target=self._beat, daemon=True).start()
            return "Heartbeat triggered."

        if sub == "interval":
            if len(parts) < 2:
                return f"Interval: {self._interval}"
            try:
                seconds = _parse_duration(parts[1])
                with self._lock:
                    self._interval = timedelta(seconds=seconds)
                return f"Interval set to {self._interval}"
            except ValueError as exc:
                return f"Invalid duration: {exc}"

        if sub == "edit":
            content = self._load_heartbeat_file()
            if not content:
                return f"No heartbeat file at {self._file_path}"
            return f"HEARTBEAT.md:\n```\n{content}\n```"

        return "Usage: heartbeat [status|trigger|interval <duration>|edit]"

    def _start_pulse(self) -> None:
        with self._lock:
            if self._running or not self._file_path:
                return
            self._running = True

        def _pulse() -> None:
            # First beat after a short delay (let everything initialize)
            self._stop_event.wait(timeout=10.0)
            while not self._stop_event.is_set():
                self._beat()
                with self._lock:
                    interval = self._interval
                self._stop_event.wait(timeout=interval.total_seconds())

        thread = threading.Thread(target=_pulse, daemon=True)
        thread.start()

    def _beat(self) -> None:
        """Perform one heartbeat cycle: read file -> ask LLM -> act if needed."""
        if self._loop is None:
            return

        content = self._load_heartbeat_file()
        if not content:
            return

        with self._lock:
            self._last_beat = datetime.now()
            self._beat_count += 1

        # Ask the LLM to evaluate the heartbeat tasks
        ctx = Context("heartbeat")
        ctx.system_prompt = _HEARTBEAT_SYSTEM_PROMPT
        ctx.set(KEY_INTERNAL_QUERY, True)
        ctx.set(KEY_STRATEGY_OVERRIDE, Strategy.PASSTHROUGH)
        init_thinking(ctx, None)

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        response = self._loop.run(ctx, f"Current time: {now}\n\n{content}")

        with self._lock:
            self._last_result = response

        # If the LLM says everything is fine, stay silent
        if response.strip() == _HEARTBEAT_OK or _HEARTBEAT_OK in response.upper():
            return

        # Log every beat
        self._log_beat(response)

        # Something needs attention -- deliver the message
        if self._on_action is not None and response.strip():
            self._on_action(response)

    def _log_beat(self, result: str) -> None:
        if self._loop is None or self._loop.dispatcher is None:
            return
        ctx = Context("heartbeat-log")
        ctx.set(KEY_INTERNAL_QUERY, True)
        status = "ok"
        if _HEARTBEAT_OK not in result.upper():
            status = "action"
        ctx.log.log_with_meta("heartbeat", result, "heartbeat", status)
        self._loop.dispatcher.dispatch(HookPoint.ON_OUTPUT, ctx)

    def _load_heartbeat_file(self) -> str:
        if not self._file_path:
            return ""
        try:
            return Path(self._file_path).read_text(encoding="utf-8").strip()
        except OSError:
            return ""


def _parse_duration(text: str) -> float:
    """Parse a Go-style duration string like '30m', '1h', '5s' into seconds."""
    text = text.strip()
    if not text:
        raise ValueError("empty duration")
    multipliers = {"s": 1, "m": 60, "h": 3600}
    if text[-1] in multipliers:
        return float(text[:-1]) * multipliers[text[-1]]
    return float(text)


_HEARTBEAT_SYSTEM_PROMPT = """Du bist ein proaktiver Agent-Hintergrundprozess.
Du bekommst eine Aufgabenliste (HEARTBEAT.md) und die aktuelle Uhrzeit.

Deine Aufgabe:
1. Pruefe jeden Eintrag: Muss JETZT etwas getan werden?
2. Wenn JA: Beschreibe kurz was zu tun ist und warum.
3. Wenn NEIN (alles in Ordnung): Antworte NUR mit HEARTBEAT_OK

Regeln:
- Sei sparsam -- nur melden wenn wirklich etwas ansteht
- Keine Smalltalk, keine Zusammenfassung wenn nichts zu tun ist
- HEARTBEAT_OK bedeutet: alles gut, nichts zu tun"""
