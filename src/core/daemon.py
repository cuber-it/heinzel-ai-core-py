"""Daemon -- signal handling, API port, lifecycle management.

Makes a Heinzel a proper service instead of a script.
"""

from __future__ import annotations

import json
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable

from core.context import Context
from core.dispatcher import Dispatcher
from core.hooks import HOOK_COUNT, HookPoint
from core.keys import all_keys
from core.loop import Loop
from core.prompt import PromptManager
from core.session import SessionManager

__all__ = ["Daemon"]


class Daemon:
    """Wraps a Dispatcher + Loop and exposes them as a service.

    Handles signals, provides an API port, manages lifecycle.
    """

    def __init__(self, name: str, dispatcher: Dispatcher, port: int = 0) -> None:
        self.name = name
        self.dispatcher = dispatcher
        self.loop = Loop(dispatcher)
        self.port = port
        self.ctx = Context(name)
        self.ctx.prompts = PromptManager()
        self.sessions = SessionManager(None, None)
        self.bind_addr: str = ""  # override listen address (default ":port")
        self.mux: dict[str, Callable[..., Any]] = {}  # extensible route table

        self._lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()
        self._server: HTTPServer | None = None

    def start(self) -> None:
        """Initialize all addons and begin listening.

        Blocks until stop() is called or a signal is received.
        """
        self.dispatcher.start_all()
        self._running = True

        # Signal handling
        def _handle_signal(signum: int, _frame: Any) -> None:
            print(f"\n{self.name}: received signal {signum}, shutting down...", file=sys.stderr)
            self.stop()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        # Session start
        session = self.sessions.start("default")
        self.ctx.session_id = session.id
        self.dispatcher.dispatch(HookPoint.ON_SESSION_START, self.ctx)

        # API port
        if self.port > 0:
            api_thread = threading.Thread(target=self._serve_api, daemon=True)
            api_thread.start()

        addon_count = len(self.dispatcher.list_addons())
        print(f"{self.name}: running (port: {self.port}, addons: {addon_count})")

        # Block until stopped
        self._stop_event.wait()

    def stop(self) -> None:
        """Gracefully shut down the daemon."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        self.sessions.end()
        self.dispatcher.stop_all()
        if self._server is not None:
            self._server.shutdown()
        self._stop_event.set()

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def _serve_api(self) -> None:
        """Start the minimal HTTP API for daemon interaction."""
        daemon = self
        extra_routes = self.mux

        class APIHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                pass

            def _json_response(self, data: Any, status: int = 200) -> None:
                body = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if self.path == "/health":
                    self._json_response({
                        "name": daemon.name,
                        "running": daemon.is_running(),
                        "addons": len(daemon.dispatcher.list_addons()),
                    })

                elif self.path == "/status":
                    self._json_response({
                        "name": daemon.name,
                        "addons": daemon.dispatcher.list_addons(),
                        "hooks": HOOK_COUNT,
                        "keys": len(all_keys()),
                    })

                elif self.path == "/addons":
                    addons_list = []
                    for addon_name in daemon.dispatcher.list_addons():
                        addon, found = daemon.dispatcher.get_addon(addon_name)
                        if found and addon is not None:
                            addons_list.append({
                                "name": addon_name,
                                "type": str(addon.type()),
                            })
                    self._json_response(addons_list)

                elif self.path in extra_routes:
                    extra_routes[self.path](self)

                else:
                    self.send_error(404)

            def do_POST(self) -> None:
                if self.path == "/chat":
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(content_length)
                    try:
                        req = json.loads(body)
                    except json.JSONDecodeError:
                        self.send_error(400, "invalid JSON")
                        return

                    message = req.get("message", "")
                    if not message:
                        self.send_error(400, "missing message")
                        return

                    with daemon._lock:
                        output = daemon.loop.run(daemon.ctx, message)

                    self._json_response({
                        "response": output,
                        "messages": len(daemon.ctx.messages),
                    })

                elif self.path == "/stop":
                    self._json_response({"status": "stopping"})
                    threading.Thread(target=daemon.stop, daemon=True).start()

                elif self.path in extra_routes:
                    extra_routes[self.path](self)

                else:
                    self.send_error(404)

        # Determine bind address
        if self.bind_addr:
            host, _, port_str = self.bind_addr.rpartition(":")
            bind_host = host or ""
            bind_port = int(port_str) if port_str else self.port
        else:
            bind_host = ""
            bind_port = self.port

        self._server = HTTPServer((bind_host, bind_port), APIHandler)
        self._server.serve_forever()
