"""Heinzel AI Core -- cognitive agent engine."""

from core.addon import Addon, AddonType, BaseAddon, Command, Result
from core.capabilities import BudgetProvider, CapabilityProvider, ProviderCapabilities
from core.config import (
    AddonConfigs,
    AddonToggle,
    Config,
    MCPServerConfig,
    MattermostConfig,
    StartupDoc,
    default_config,
    load_config,
)
from core.context import Context, Message, ToolCall
from core.daemon import Daemon
from core.dispatcher import Dispatcher
from core.factory import (
    OPTIONAL_ADDONS,
    PFLICHT_ADDONS,
    AddonBuilder,
    AddonEntry,
    BuildResult,
    Factory,
    is_addon_enabled,
    permissions_path,
    register_addon_builder,
)
from core.heartbeat import HeartbeatAddon, HeartbeatConfig
from core.hooks import HOOK_COUNT, HookPoint
from core.iobridge import IOBridge, IORegistry
from core.keys import (
    KEY_INTERNAL_QUERY,
    KEY_NEEDS_RERUN,
    KEY_STRATEGY_OVERRIDE,
    KEY_THINKING,
    KeyDef,
    KeyRegistry,
    all_keys,
    is_registered,
    must_get_key,
    register_key,
)
from core.log import LogLevel, Logger
from core.mcp import Tool, ToolRegistry
from core.memcaps import MemoryCapabilities, MemoryCapabilityProvider
from core.prompt import ChatEntry, ChatLog, PromptBlock, PromptLayer, PromptManager
from core.session import Session, SessionManager
from core.reasoning import (
    Checkpoint,
    Strategy,
    ThinkingStep,
    ThinkingStream,
    get_thinking,
    init_thinking,
)

__all__ = [
    # addon
    "Addon", "AddonType", "BaseAddon", "Command", "Result",
    # capabilities
    "BudgetProvider", "CapabilityProvider", "ProviderCapabilities",
    # config
    "AddonConfigs", "AddonToggle", "Config", "MCPServerConfig",
    "MattermostConfig", "StartupDoc", "default_config", "load_config",
    # context
    "Context", "Message", "ToolCall",
    # daemon
    "Daemon",
    # dispatcher
    "Dispatcher",
    # factory
    "OPTIONAL_ADDONS", "PFLICHT_ADDONS", "AddonBuilder", "AddonEntry",
    "BuildResult", "Factory", "is_addon_enabled", "permissions_path",
    "register_addon_builder",
    # heartbeat
    "HeartbeatAddon", "HeartbeatConfig",
    # hooks
    "HOOK_COUNT", "HookPoint",
    # iobridge
    "IOBridge", "IORegistry",
    # keys
    "KEY_INTERNAL_QUERY", "KEY_NEEDS_RERUN", "KEY_STRATEGY_OVERRIDE",
    "KEY_THINKING", "KeyDef", "KeyRegistry", "all_keys", "is_registered",
    "must_get_key", "register_key",
    # log
    "LogLevel", "Logger",
    # mcp
    "Tool", "ToolRegistry",
    # memcaps
    "MemoryCapabilities", "MemoryCapabilityProvider",
    # prompt
    "ChatEntry", "ChatLog", "PromptBlock", "PromptLayer", "PromptManager",
    # session
    "Session", "SessionManager",
    # reasoning
    "Checkpoint", "Strategy", "ThinkingStep", "ThinkingStream",
    "get_thinking", "init_thinking",
]
