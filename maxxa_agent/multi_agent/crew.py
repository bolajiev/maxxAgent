"""
Crew orchestration container for multi-agent workflows.

The Crew owns:
- multiple agent definitions (name/role/system_prompt/tools/memory)
- delegation support (agents can ask other agents for help)

The underlying execution unit is the core `maxxa_agent.core.agent.Agent`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from maxxa_agent.core.agent import Agent
from maxxa_agent.core.config import AgentConfig
from maxxa_agent.core.memory import ConversationMemory
from maxxa_agent.core.tools import ToolResult, ToolRunStatus, ToolSpec
from maxxa_agent.multi_agent.task import Task, TaskResult


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """
    Multi-agent wrapper around a core Agent.

    Args:
        name: Stable unique name (used for routing/delegation).
        role: Human-readable role/specialization label.
        agent: Underlying single-agent `Agent` instance.
    """

    name: str
    role: str
    agent: Agent


class Crew:
    """
    Holds multiple specialized agents and provides coordination helpers.

    Delegation support:
    - The Crew can inject a `delegate` tool into each agent, enabling a model to
      ask for help from other agents via tool-calls.
    """

    def __init__(self, *, agents: Iterable[AgentDefinition]) -> None:
        self._agents: dict[str, AgentDefinition] = {}
        for a in agents:
            if a.name in self._agents:
                raise ValueError(f"Duplicate agent name: {a.name}")
            self._agents[a.name] = a

    def list_agents(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def get_agent(self, name: str) -> AgentDefinition:
        try:
            return self._agents[name]
        except KeyError as e:
            raise KeyError(f"Unknown agent: {name}") from e

    def run_task(self, task: Task) -> TaskResult:
        agent_def = self.get_agent(task.assigned_agent)
        prompt = self._task_to_prompt(task, agent_def)
        try:
            output = agent_def.agent.run(prompt)
            return TaskResult(task_id=task.task_id, agent_name=agent_def.name, output=output, success=True)
        except Exception as e:  # noqa: BLE001
            return TaskResult(
                task_id=task.task_id,
                agent_name=agent_def.name,
                output="",
                success=False,
                error=f"{type(e).__name__}: {e}",
            )

    def enable_delegation_tools(self) -> None:
        """
        Inject a `delegate` tool into each agent's ToolRegistry.

        Schema:
          {"agent": "<target agent name>", "task": "<task description>"}
        """

        def make_delegate_handler(from_agent: str):
            def handler(args: dict[str, Any]) -> ToolResult:
                target = args["agent"]
                subtask_desc = args["task"]
                task = Task(description=subtask_desc, assigned_agent=target, context={"delegated_by": from_agent})
                result = self.run_task(task)
                if not result.success:
                    return ToolResult(
                        status=ToolRunStatus.ERROR,
                        error=result.error,
                        result={"task_id": result.task_id},
                    )
                return ToolResult(result={"task_id": result.task_id, "output": result.output})

            return handler

        for agent_def in self._agents.values():
            if agent_def.agent.tools.has("delegate"):
                continue
            agent_def.agent.tools.register(
                ToolSpec(
                    name="delegate",
                    description="Ask another named agent for help on a subtask.",
                    args_schema={
                        "type": "object",
                        "properties": {
                            "agent": {"type": "string", "minLength": 1},
                            "task": {"type": "string", "minLength": 1},
                        },
                        "required": ["agent", "task"],
                        "additionalProperties": False,
                    },
                    handler=make_delegate_handler(agent_def.name),
                    is_dangerous=False,
                )
            )

    @staticmethod
    def _task_to_prompt(task: Task, agent_def: AgentDefinition) -> str:
        parts: list[str] = []
        parts.append(f"Task for agent '{agent_def.name}' ({agent_def.role}):")
        parts.append(task.description.strip())
        if task.context is not None:
            parts.append("\nContext:")
            parts.append(str(task.context))
        return "\n".join(parts).strip()


def make_agent_definition(
    *,
    name: str,
    role: str,
    base_agent: Agent,
    system_prompt: str | None = None,
) -> AgentDefinition:
    """
    Convenience helper to specialize an existing Agent instance.

    If `system_prompt` is provided, creates a specialized Agent with its own memory.
    """
    if system_prompt is None:
        return AgentDefinition(name=name, role=role, agent=base_agent)

    cfg = AgentConfig(
        backend=base_agent.config.backend,
        tools=base_agent.config.tools,
        memory=base_agent.config.memory,
        max_steps=base_agent.config.max_steps,
        temperature=base_agent.config.temperature,
        system_prompt=system_prompt,
    )
    specialized = Agent(
        llm=base_agent.llm,
        config=cfg,
        tools=base_agent.tools,
        memory=ConversationMemory(
            window_size=cfg.memory.window_size,
            summary_trigger_count=cfg.memory.summary_trigger_count,
        ),
    )
    return AgentDefinition(name=name, role=role, agent=specialized)

