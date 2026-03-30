---
title: Heinzel AI Core (Python)
aliases: [heinzel-core-py]
tags:
  - heinzel
  - core
  - engine
  - python
type: spec
status: active
created: 2026-03-29
modified: 2026-03-30
project: heinzel-ai-core-py
---

# Heinzel AI Core

Cognitive agent engine. The foundation for all Heinzel agents. Python implementation.

## What it is

A minimal, extensible engine for building cognitive AI agents. The core provides the execution loop, hook-based addon dispatch, prompt composition, session management, and daemon infrastructure. Everything else -- reasoning strategies, memory, tools, UIs -- are addons.

This is a port of [heinzel-ai-core-go](https://github.com/cuber-it/heinzel-ai-core-go). Same architecture, same 24 hook points, Python idioms.

## Architecture

```
Loop: Input -> Classify -> Memory -> Context -> LLM -> Tools -> Output
         ^                                                    |
         +------------------ 24 Hook Points -----------------+
                    (Addons plug in here)
```

The core is deliberately small (~1500 LOC). It provides:

- **Loop** -- The cognitive cycle. Input in, output out. Exception-safe.
- **Dispatcher** -- Priority-ordered addon dispatch on 24 hook points.
- **Context** -- Mutable pipeline state shared across all addons per turn.
- **Prompt Manager** -- 4-layer prompt composition (System, Session, User, Turn).
- **SessionManager** -- Session lifecycle, persistence, restore. Tracks conversation state across daemon restarts.
- **Daemon** -- Signal handling, HTTP API, configurable bind address, session management. Makes an agent a service.
- **Heartbeat** -- Proactive background pulse. The agent acts without being asked.
- **Key Registry** -- Typed, validated context keys. No magic strings.
- **Strategy & Thinking** -- Strategy enum and ThinkingStream for visible reasoning.
- **Internal Query** -- Fast-path for addon-to-LLM queries that bypass the full hook pipeline.

## Quick Start

### Install

```bash
pip install -e .
```

### As a Library

```python
from core import Dispatcher, Loop, Context

dispatcher = Dispatcher()
# dispatcher.register(my_provider, 100)
# dispatcher.register(my_addon, 10)
dispatcher.start_all()

loop = Loop(dispatcher)
ctx = Context("my-agent")
output = loop.run(ctx, "Hello")
```

### As a Daemon (headless)

```python
from core import Daemon, Dispatcher

dispatcher = Dispatcher()
# ... register provider and addons ...

daemon = Daemon("riker", dispatcher, 12001)
daemon.set_bind_address("0.0.0.0")  # default: localhost
daemon.start()  # blocks, handles signals, serves API
```

API endpoints:
- `GET  /health` -- Is the agent alive?
- `GET  /status` -- Addons, hooks, keys
- `GET  /addons` -- List loaded addons
- `POST /chat`   -- Send a message, get a response
- `POST /stop`   -- Graceful shutdown

## Tests

75 tests covering the core engine, dispatcher, context, prompt manager, session management, and daemon.

```bash
pytest
```

## Project Structure

```
src/core/    Engine -- Loop, Dispatcher, Context, Hooks, Daemon, SessionManager, Heartbeat
tests/       Test suite
```

## Design Principles

- The core does not depend on any addon
- Addons are independent -- no cross-addon imports
- All LLM calls go through the provider (no direct API calls)
- All LLM calls go through the loop (no addon bypasses the pipeline)
- Context keys are registered and typed -- no magic strings
- The heartbeat is a core feature, not an addon -- agents are proactive by design

## Related

- [heinzel-ai-core-go](https://github.com/cuber-it/heinzel-ai-core-go) -- Go reference implementation
- [heinzel-ai-addons-py](https://github.com/cuber-it/heinzel-ai-addons-py) -- Official addon collection (Python)
- [heinzel-ai-addons-go](https://github.com/cuber-it/heinzel-ai-addons-go) -- Official addon collection (Go)
- [heinzel-assistant](https://github.com/cuber-it/heinzel-assistant) -- Consumer agent ("Your Personal Heinzel")
- [heinzel-crew](https://github.com/cuber-it/heinzel-crew) -- Multi-agent team (Riker, Data, Scotty)

## License

Apache 2.0 -- see [LICENSE](LICENSE)

Built with assistance from Claude (Anthropic).
