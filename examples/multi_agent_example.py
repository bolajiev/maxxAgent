"""
Multi-agent example: Researcher + Coder + Reviewer coordinated by a Crew.

This script uses a tiny scripted LLM backend so it can run without external keys.
Swap `ScriptedLLM()` for a real backend (OpenAI/HF/custom endpoint) to go live.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Allow running from a source checkout without installation.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from maxxa_agent.core.agent import Agent
from maxxa_agent.core.config import AgentConfig, BackendConfig
from maxxa_agent.core.tools import ToolRegistry
from maxxa_agent.multi_agent.crew import AgentDefinition, Crew
from maxxa_agent.multi_agent.orchestrator import Orchestrator
from maxxa_agent.multi_agent.task import Task


@dataclass(frozen=True, slots=True)
class ScriptedLLM:
    """
    Deterministic backend for demos.

    It produces a valid ReAct response with `[FINAL_ANSWER]` only, based on the
    role marker embedded in each agent's system prompt.
    """

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> str:
        role = "generalist"
        if "ROLE: Researcher" in prompt:
            role = "researcher"
        elif "ROLE: Coder" in prompt:
            role = "coder"
        elif "ROLE: Reviewer" in prompt:
            role = "reviewer"

        if role == "researcher":
            answer = (
                "Key points:\n"
                "- Prefer clear interfaces and typed results.\n"
                "- Keep dangerous tools disabled by default.\n"
                "- Add timeouts and output limits for tool calls.\n"
            )
        elif role == "coder":
            answer = (
                "Implementation plan:\n"
                "- Add new module(s) and wire into registry.\n"
                "- Write minimal tests/examples.\n"
                "- Ensure imports and type hints are clean.\n"
            )
        elif role == "reviewer":
            answer = (
                "Review notes:\n"
                "- Watch for shared mutable state across agents.\n"
                "- Ensure orchestration preserves ordering when needed.\n"
                "- Avoid unsafe defaults for file/code tools.\n"
            )
        else:
            answer = "Done."

        return f"[THOUGHT] I will answer as the {role}.\n[FINAL_ANSWER] {answer}"


def main() -> None:
    llm = ScriptedLLM()

    # Each agent gets its own tool registry + memory, but can share the same backend.
    def make_agent(system_prompt: str) -> Agent:
        cfg = AgentConfig(
            backend=BackendConfig(name="scripted"),
            system_prompt=system_prompt,
            max_steps=5,
            temperature=0.0,
        )
        tools = ToolRegistry.with_builtins(workspace_root=".", enable_code_execution=False)
        return Agent(llm=llm, config=cfg, tools=tools)

    researcher = AgentDefinition(
        name="Researcher",
        role="Search + summarize",
        agent=make_agent("ROLE: Researcher\nYou research and summarize succinctly."),
    )
    coder = AgentDefinition(
        name="Coder",
        role="Turn research into code changes",
        agent=make_agent("ROLE: Coder\nYou write clean, production-grade code."),
    )
    reviewer = AgentDefinition(
        name="Reviewer",
        role="Review for correctness and safety",
        agent=make_agent("ROLE: Reviewer\nYou review code for quality and risks."),
    )

    crew = Crew(agents=[researcher, coder, reviewer])
    orchestrator = Orchestrator(crew=crew)

    tasks = [
        Task(description="Research best practices for safe tool execution.", assigned_agent="Researcher"),
        Task(description="Draft implementation steps based on the research.", assigned_agent="Coder"),
        Task(description="Review the draft for safety and design issues.", assigned_agent="Reviewer"),
    ]

    result = orchestrator.run_sequential(tasks)
    print(result.aggregated_output)


if __name__ == "__main__":
    main()

