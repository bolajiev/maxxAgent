"""
Configuration dataclasses for MaxxAgentFramework.

These configs are intentionally small and explicit: they define safe defaults,
and the Agent/ToolRegistry/backends can consume them without hidden globals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True, slots=True)
class BackendConfig:
    """
    LLM backend configuration.

    `name` selects the backend implementation; `options` may carry backend-specific
    settings (API keys, endpoints, model IDs, etc.). Backends should validate and
    surface missing/invalid fields with clear errors at construction time.
    """

    name: str = "custom"
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolConfig:
    """Tool execution settings and safety toggles."""

    timeout_s: float = 20.0
    max_output_chars: int = 50_000
    allow_dangerous_tools: bool = False
    enable_code_execution: bool = False


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    """Memory settings."""

    window_size: int = 5
    summary_trigger_count: int = 30


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Top-level agent configuration."""

    backend: BackendConfig = field(default_factory=BackendConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)

    max_steps: int = 10
    temperature: float = 0.2

    system_prompt: str = (
        "You are MaxxAgentFramework. Use the ReAct format strictly:\n"
        "[THOUGHT] ...\n"
        "[ACTION] {\"tool\": \"name\", \"args\": {...}}  (optional)\n"
        "[OBSERVATION] ... (after tool runs)\n"
        "[FINAL_ANSWER] ... (when done)\n"
    )

    def validate(self) -> None:
        if self.max_steps <= 0:
            raise ValueError("max_steps must be > 0")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("temperature must be in [0.0, 2.0]")
        if self.tools.timeout_s <= 0:
            raise ValueError("tools.timeout_s must be > 0")
        if self.tools.max_output_chars <= 0:
            raise ValueError("tools.max_output_chars must be > 0")
        if self.memory.window_size <= 0:
            raise ValueError("memory.window_size must be > 0")
        if self.memory.summary_trigger_count <= 0:
            raise ValueError("memory.summary_trigger_count must be > 0")

