"""YAML configuration loading and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

__all__ = [
    "Config",
    "MattermostConfig",
    "AddonConfigs",
    "AddonToggle",
    "StartupDoc",
    "MCPServerConfig",
    "load_config",
    "default_config",
]


@dataclass
class AddonToggle:
    """nil = use default (enabled), False = disabled."""

    enabled: bool = True

    def is_enabled(self) -> bool:
        return self.enabled


@dataclass
class MattermostConfig:
    """Mattermost connection settings."""

    url: str = ""
    token: str = ""
    channels: list[str] = field(default_factory=list)
    team: str = ""
    mention_only: bool = False


@dataclass
class StartupDoc:
    """A markdown file loaded at session start."""

    path: str = ""
    layer: str = "session"
    optional: bool = False
    priority: int = 50


@dataclass
class MCPServerConfig:
    """An MCP server to load at startup."""

    name: str = ""
    type: str = ""        # "http" or "stdio"
    url: str = ""         # for HTTP
    command: str = ""     # for stdio
    args: list[str] = field(default_factory=list)


@dataclass
class AddonConfigs:
    """Controls which optional addons are loaded."""

    reasoning: AddonToggle | None = None
    memory_composer: AddonToggle | None = None
    compaction: AddonToggle | None = None
    websearch: AddonToggle | None = None
    file_upload: AddonToggle | None = None
    mcp_manager: AddonToggle | None = None
    chatlog: AddonToggle | None = None
    transcript: AddonToggle | None = None
    logger: AddonToggle | None = None
    heartbeat: AddonToggle | None = None
    cognitive_memory: AddonToggle | None = None

    def is_enabled(self, name: str) -> bool:
        toggle = getattr(self, name, None)
        if toggle is None:
            return True
        return toggle.is_enabled()


@dataclass
class Config:
    """Holds all neo-heinzel configuration."""

    # Agent
    agent_name: str = "Neo-Heinzel"
    agent_version: str = ""

    # Prompts
    prompts_system: str = ""
    prompts_session: str = ""
    prompts_user: str = ""
    prompts_skill_dirs: list[str] = field(default_factory=list)

    # Provider
    provider_type: str = "echo"
    provider_model: str = ""
    provider_url: str = ""

    # Context
    context_token_budget: int = 200_000

    # CostGuard
    costguard_max_tokens_per_turn: int = 0
    costguard_max_tokens_per_session: int = 0
    costguard_max_tokens_per_day: int = 0
    costguard_max_cost_per_day: float = 0.0
    costguard_max_deep_per_session: int = 0

    # WebSearch
    websearch_engine: str = ""
    websearch_url: str = ""
    websearch_api_key: str = ""

    # Recovery
    recovery_max_retries: int = 2
    recovery_circuit_timeout: int = 60
    recovery_on_provider_fail: str = ""
    recovery_on_tool_fail: str = ""
    recovery_on_search_fail: str = ""

    # Startup docs
    startup_docs: list[StartupDoc] = field(default_factory=list)

    # MCP servers
    mcp_servers: list[MCPServerConfig] = field(default_factory=list)

    # Logging
    logging_verbose: bool = False
    logging_thinking: bool = False
    logging_log_dir: str = ""

    # Mattermost
    mattermost: MattermostConfig = field(default_factory=MattermostConfig)

    # Heartbeat
    heartbeat_interval: str = ""
    heartbeat_file: str = ""

    # Cognitive Memory
    memory_llm_endpoint: str = ""
    memory_llm_model: str = ""
    memory_prolog_url: str = ""
    memory_vault_url: str = ""
    memory_script_url: str = ""

    # Addons
    addons: AddonConfigs = field(default_factory=AddonConfigs)

    def validate(self) -> None:
        errors: list[str] = []

        # Provider
        if not self.provider_type:
            errors.append("provider.type must not be empty")
        if self.provider_url and not (
            self.provider_url.startswith("http://")
            or self.provider_url.startswith("https://")
        ):
            errors.append(
                f"provider.url must start with http:// or https://, got {self.provider_url!r}"
            )

        # CostGuard -- non-negative limits
        if self.costguard_max_tokens_per_turn < 0:
            errors.append("costguard.max_tokens_per_turn must not be negative")
        if self.costguard_max_tokens_per_session < 0:
            errors.append("costguard.max_tokens_per_session must not be negative")
        if self.costguard_max_tokens_per_day < 0:
            errors.append("costguard.max_tokens_per_day must not be negative")
        if self.costguard_max_cost_per_day < 0:
            errors.append("costguard.max_cost_per_day must not be negative")
        if self.costguard_max_deep_per_session < 0:
            errors.append("costguard.max_deep_per_session must not be negative")

        # Logging
        if not self.logging_log_dir:
            errors.append("logging.log_dir must not be empty")

        # WebSearch engine
        valid_engines = {"", "searxng", "brave", "ddg", "none"}
        if self.websearch_engine not in valid_engines:
            errors.append(
                f"websearch.engine must be one of: searxng, brave, ddg, none -- got {self.websearch_engine!r}"
            )

        # MCP servers
        for index, server in enumerate(self.mcp_servers):
            prefix = f"mcp_servers[{index}]"
            if not server.name:
                errors.append(f"{prefix}.name must not be empty")
            if server.type not in ("http", "stdio"):
                errors.append(f'{prefix}.type must be "http" or "stdio", got {server.type!r}')
            if server.type == "http" and not server.url:
                errors.append(f'{prefix}.url is required for type "http"')
            if server.type == "stdio" and not server.command:
                errors.append(f'{prefix}.command is required for type "stdio"')

        if errors:
            raise ValueError("config validation failed:\n- " + "\n- ".join(errors))


def _expand_env_if(value: str) -> str:
    if value.startswith("$"):
        return os.path.expandvars(value)
    return value


def _parse_addon_toggle(raw: dict | bool | None) -> AddonToggle | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return AddonToggle(enabled=raw)
    if isinstance(raw, dict):
        return AddonToggle(enabled=raw.get("enabled", True))
    return None


def load_config(path: str) -> Config:
    """Read a YAML config file and return a Config."""
    content = Path(path).read_text(encoding="utf-8")

    # Expand ~ in paths
    home = str(Path.home())
    content = content.replace("~/", home + "/")

    raw = yaml.safe_load(content) or {}

    config = Config()

    # Agent
    agent = raw.get("agent", {})
    config.agent_name = agent.get("name", config.agent_name)
    config.agent_version = agent.get("version", config.agent_version)

    # Prompts
    prompts = raw.get("prompts", {})
    config.prompts_system = prompts.get("system", "")
    config.prompts_session = prompts.get("session", "")
    config.prompts_user = prompts.get("user", "")
    config.prompts_skill_dirs = prompts.get("skill_dirs", [])

    # Provider
    provider = raw.get("provider", {})
    config.provider_type = provider.get("type", config.provider_type)
    config.provider_model = provider.get("model", "")
    config.provider_url = provider.get("url", "")

    # Context
    context = raw.get("context", {})
    config.context_token_budget = context.get("token_budget", config.context_token_budget)

    # CostGuard
    costguard = raw.get("costguard", {})
    config.costguard_max_tokens_per_turn = costguard.get("max_tokens_per_turn", 0)
    config.costguard_max_tokens_per_session = costguard.get("max_tokens_per_session", 0)
    config.costguard_max_tokens_per_day = costguard.get("max_tokens_per_day", 0)
    config.costguard_max_cost_per_day = costguard.get("max_cost_per_day", 0.0)
    config.costguard_max_deep_per_session = costguard.get("max_deep_per_session", 0)

    # WebSearch
    websearch = raw.get("websearch", {})
    config.websearch_engine = websearch.get("engine", "")
    config.websearch_url = websearch.get("url", "")
    config.websearch_api_key = websearch.get("api_key", "")

    # Recovery
    recovery = raw.get("recovery", {})
    config.recovery_max_retries = recovery.get("max_retries", 2)
    config.recovery_circuit_timeout = recovery.get("circuit_timeout", 60)
    config.recovery_on_provider_fail = recovery.get("on_provider_fail", "")
    config.recovery_on_tool_fail = recovery.get("on_tool_fail", "")
    config.recovery_on_search_fail = recovery.get("on_search_fail", "")

    # Startup docs
    for doc_raw in raw.get("startup_docs", []):
        config.startup_docs.append(StartupDoc(
            path=doc_raw.get("path", ""),
            layer=doc_raw.get("layer", "session"),
            optional=doc_raw.get("optional", False),
            priority=doc_raw.get("priority", 50),
        ))

    # MCP servers
    for server_raw in raw.get("mcp_servers", []):
        config.mcp_servers.append(MCPServerConfig(
            name=server_raw.get("name", ""),
            type=server_raw.get("type", ""),
            url=server_raw.get("url", ""),
            command=server_raw.get("command", ""),
            args=server_raw.get("args", []),
        ))

    # Logging
    logging_raw = raw.get("logging", {})
    config.logging_verbose = logging_raw.get("verbose", False)
    config.logging_thinking = logging_raw.get("thinking", False)
    config.logging_log_dir = logging_raw.get("log_dir", "")

    # Mattermost
    mm = raw.get("mattermost", {})
    config.mattermost = MattermostConfig(
        url=mm.get("url", ""),
        token=mm.get("token", ""),
        channels=mm.get("channels", []),
        team=mm.get("team", ""),
        mention_only=mm.get("mention_only", False),
    )

    # Heartbeat
    heartbeat = raw.get("heartbeat", {})
    config.heartbeat_interval = heartbeat.get("interval", "")
    config.heartbeat_file = heartbeat.get("file", "")

    # Memory
    memory = raw.get("memory", {})
    config.memory_llm_endpoint = memory.get("llm_endpoint", "")
    config.memory_llm_model = memory.get("llm_model", "")
    config.memory_prolog_url = memory.get("prolog_url", "")
    config.memory_vault_url = memory.get("vault_url", "")
    config.memory_script_url = memory.get("script_url", "")

    # Addons
    addons_raw = raw.get("addons", {})
    config.addons = AddonConfigs(
        reasoning=_parse_addon_toggle(addons_raw.get("reasoning")),
        memory_composer=_parse_addon_toggle(addons_raw.get("memory_composer")),
        compaction=_parse_addon_toggle(addons_raw.get("compaction")),
        websearch=_parse_addon_toggle(addons_raw.get("websearch")),
        file_upload=_parse_addon_toggle(addons_raw.get("file_upload")),
        mcp_manager=_parse_addon_toggle(addons_raw.get("mcp_manager")),
        chatlog=_parse_addon_toggle(addons_raw.get("chatlog")),
        transcript=_parse_addon_toggle(addons_raw.get("transcript")),
        logger=_parse_addon_toggle(addons_raw.get("logger")),
        heartbeat=_parse_addon_toggle(addons_raw.get("heartbeat")),
        cognitive_memory=_parse_addon_toggle(addons_raw.get("cognitive_memory")),
    )

    # Defaults
    if not config.agent_name:
        config.agent_name = "Neo-Heinzel"
    if not config.provider_type:
        config.provider_type = "echo"
    if config.context_token_budget == 0:
        config.context_token_budget = 200_000
    if not config.logging_log_dir:
        config.logging_log_dir = str(Path.home() / ".neo-heinzel" / "logs")

    # Expand environment variables in sensitive fields
    config.provider_url = _expand_env_if(config.provider_url)
    config.websearch_url = _expand_env_if(config.websearch_url)
    config.websearch_api_key = _expand_env_if(config.websearch_api_key)
    config.mattermost.token = _expand_env_if(config.mattermost.token)
    config.mattermost.url = _expand_env_if(config.mattermost.url)

    config.validate()
    return config


def default_config() -> Config:
    """Return a config with sensible defaults."""
    config = Config()
    config.agent_name = "Neo-Heinzel"
    config.agent_version = "0.1"
    config.provider_type = "echo"
    config.context_token_budget = 200_000
    config.logging_thinking = True
    config.logging_log_dir = str(Path.home() / ".neo-heinzel" / "logs")
    config.prompts_system = (
        "Du bist Neo-Heinzel, ein kognitiver Agent. "
        "Antworte praezise und hilfreich auf Deutsch."
    )
    return config
