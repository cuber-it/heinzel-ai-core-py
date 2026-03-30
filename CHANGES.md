# Changes

## 0.1.0 -- 2026-03-29

Initial release. Python port of heinzel-ai-core-go.

### Core Engine
- Loop: 24-hook cognitive cycle (Input -> Classify -> Memory -> Context -> LLM -> Tools -> Output)
- Dispatcher: priority-ordered addon dispatch, register/unregister at runtime
- Context: mutable pipeline state with typed key registry
- Prompt Manager: 4-layer composition (System, Session, User, Turn)
- Factory: config-driven addon loading via builder registry
- Strategy: 5 reasoning strategies (Passthrough, CoT, Deep, ReAct, Native)
- ThinkingStream: visible reasoning steps, streamed live
- Heartbeat: proactive background pulse with configurable interval
- Daemon: signal handling, HTTP API (/health, /status, /chat, /stop), session management
- Logger: structured stderr logging with levels
- Key Registry: typed, validated context keys -- no magic strings
- Config: YAML loading with env var expansion and validation
