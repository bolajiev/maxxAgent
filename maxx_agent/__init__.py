"""
Maxx Agent Framework — build agents that think, act, and remember.

Quick start::

    from maxx_agent import Agent, AgentConfig
    from maxx_agent.backends import CustomEndpointClient
"""

from __future__ import annotations

from maxx_agent.core.agent import Agent, AgentParseError, RunTrace, StepLog
from maxx_agent.core.config import AgentConfig, BackendConfig, MemoryConfig, ToolConfig
from maxx_agent.core.memory import ConversationMemory, Message
from maxx_agent.core.tools import ToolRegistry, ToolResult, ToolRunStatus, ToolSpec

__all__ = [
    "__version__",
    # Agent
    "Agent",
    "AgentParseError",
    "RunTrace",
    "StepLog",
    # Config
    "AgentConfig",
    "BackendConfig",
    "MemoryConfig",
    "ToolConfig",
    # Memory
    "ConversationMemory",
    "Message",
    # Tools
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "ToolRunStatus",
]

__version__ = "0.1.0"
