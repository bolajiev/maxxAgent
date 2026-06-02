"""
Task and result primitives for multi-agent orchestration.

These dataclasses intentionally stay lightweight and serializable so they can
be logged, stored, or passed between agents and orchestration layers.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True, slots=True)
class Task:
    """
    A unit of work executed by a named agent.

    Args:
        description: Human-readable task description.
        assigned_agent: Name of the agent expected to execute this task.
        task_id: Optional explicit id. If omitted, a UUID is generated.
        created_at_s: UNIX timestamp in seconds.
        context: Optional free-form context to pass to the agent (string or dict).
        metadata: Additional structured metadata for tracing/routing.
    """

    description: str
    assigned_agent: str
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at_s: float = field(default_factory=lambda: time.time())
    context: Optional[Any] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskResult:
    """
    Result of running a Task with an agent.

    Args:
        task_id: Corresponding Task id.
        agent_name: Name of agent that produced the result.
        output: Primary textual output.
        success: Whether the run succeeded.
        error: Optional error message.
        artifacts: Optional structured outputs (e.g. files changed, URLs found).
        metadata: Execution metadata (timing, retries, etc.).
    """

    task_id: str
    agent_name: str
    output: str
    success: bool = True
    error: Optional[str] = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

