"""
Main Agent class for MaxxAgentFramework.

The Agent runs a stateful ReAct-style loop:
  - Build prompt from system prompt + memory + user query
  - Call LLM
  - Parse tagged blocks: [THOUGHT], [ACTION], [OBSERVATION], [FINAL_ANSWER]
  - If an [ACTION] tool call is detected, execute it via ToolRegistry
  - Append observations to memory and iterate until [FINAL_ANSWER] or max steps
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from maxxa_agent.backends.llm_client import LLMClient
from maxxa_agent.core.config import AgentConfig
from maxxa_agent.core.memory import ConversationMemory, Message
from maxxa_agent.core.tools import ToolRegistry, ToolRunOptions, ToolResult, ToolRunStatus


class AgentParseError(RuntimeError):
    """Raised when the model output cannot be parsed into the expected ReAct format."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    tool: str
    args: dict[str, Any]

@dataclass(frozen=True, slots=True)
class StepLog:
    """Structured trace of a single agent step."""

    step: int
    prompt: str
    raw_model_output: str
    thought: Optional[str]
    action: Optional[dict[str, Any]]
    observation: Optional[dict[str, Any]]
    final_answer: Optional[str]


@dataclass(frozen=True, slots=True)
class RunTrace:
    """Full trace of a run (steps + final output)."""

    final_answer: str
    steps: list[StepLog]


_TAG_RE = re.compile(
    r"(?s)\[(THOUGHT|ACTION|OBSERVATION|FINAL_ANSWER)\]\s*(.*?)(?=\n\[(THOUGHT|ACTION|OBSERVATION|FINAL_ANSWER)\]|\Z)"
)


def _extract_blocks(text: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    for m in _TAG_RE.finditer(text.strip()):
        tag = m.group(1)
        content = m.group(2).strip()
        blocks[tag] = content
    return blocks


def _parse_action(action_text: str) -> ToolCall:
    """
    Parse `[ACTION]` content.

    Expected JSON:
      {"tool": "name", "args": {...}}
    """
    try:
        data = json.loads(action_text)
    except json.JSONDecodeError as e:
        raise AgentParseError(f"[ACTION] must be JSON: {e}") from e
    if not isinstance(data, dict):
        raise AgentParseError("[ACTION] JSON must be an object.")
    tool = data.get("tool")
    args = data.get("args", {})
    if not isinstance(tool, str) or not tool:
        raise AgentParseError("[ACTION].tool must be a non-empty string.")
    if not isinstance(args, dict):
        raise AgentParseError("[ACTION].args must be a JSON object.")
    return ToolCall(tool=tool, args=args)


class Agent:
    """
    MaxxAgentFramework agent.

    Args:
        llm: LLM backend implementing `LLMClient`.
        config: Agent configuration (max steps, temperature, system prompt, etc.).
        tools: ToolRegistry (optional). If omitted, a new empty registry is created.
        memory: ConversationMemory (optional). If omitted, a new memory store is created.
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        config: Optional[AgentConfig] = None,
        tools: Optional[ToolRegistry] = None,
        memory: Optional[ConversationMemory] = None,
    ) -> None:
        self.llm = llm
        self.config = config or AgentConfig()
        self.config.validate()
        self.tools = tools or ToolRegistry()
        self.memory = memory or ConversationMemory(
            window_size=self.config.memory.window_size,
            summary_trigger_count=self.config.memory.summary_trigger_count,
        )

    def build_prompt(self, user_query: str) -> str:
        """
        Build the prompt text for the backend.

        This is a provider-agnostic plain-text prompt designed to work well
        across completion/chat backends.
        """
        blocks = []
        blocks.append(self.config.system_prompt.strip())

        for b in self.memory.to_prompt_blocks():
            role = b["role"]
            content = b["content"]
            blocks.append(f"[{role.upper()}]\n{content}".strip())

        blocks.append(f"[USER]\n{user_query}".strip())
        blocks.append(
            "Respond using ONLY the tags [THOUGHT], [ACTION], [OBSERVATION], [FINAL_ANSWER]. "
            "Use [ACTION] only when you need to call a tool."
        )
        return "\n\n".join(blocks).strip() + "\n"

    def run(self, user_query: str) -> str:
        """
        Run the agent loop and return the final answer.

        Raises:
            AgentParseError: if the model output cannot be parsed reliably.
            RuntimeError: if max steps is exceeded without [FINAL_ANSWER].
        """
        self.memory.add(Message(role="user", content=user_query))

        for step in range(1, self.config.max_steps + 1):
            prompt = self.build_prompt(user_query=user_query)
            raw = self.llm.generate(prompt, temperature=self.config.temperature)
            self.memory.add(Message(role="assistant", content=raw, metadata={"step": step}))

            blocks = _extract_blocks(raw)

            if "FINAL_ANSWER" in blocks and blocks["FINAL_ANSWER"]:
                final = blocks["FINAL_ANSWER"].strip()
                self.memory.add(Message(role="assistant", content=final, metadata={"final": True}))
                return final

            if "ACTION" not in blocks or not blocks["ACTION"]:
                raise AgentParseError(
                    "Model output missing [ACTION] and [FINAL_ANSWER]. "
                    "Ensure the backend prompt enforces the tag format."
                )

            call = _parse_action(blocks["ACTION"])

            tool_opts = ToolRunOptions(
                timeout_s=self.config.tools.timeout_s,
                max_output_chars=self.config.tools.max_output_chars,
                allow_dangerous_tools=self.config.tools.allow_dangerous_tools,
            )
            result: ToolResult = self.tools.run(call.tool, call.args, options=tool_opts)

            obs_payload = result.to_json()
            obs_text = json.dumps(obs_payload, ensure_ascii=False)
            self.memory.add(
                Message(
                    role="tool",
                    content=f"[OBSERVATION]\n{obs_text}",
                    metadata={"tool": call.tool, "status": result.status.value, "step": step},
                )
            )

            # Make the tool observation available to the next step as context.
            user_query = user_query

            # If tool timed out or errored, continue looping; model can recover.
            if result.status in (ToolRunStatus.ERROR, ToolRunStatus.TIMEOUT, ToolRunStatus.INVALID_ARGS):
                continue

        raise RuntimeError(f"Max steps exceeded ({self.config.max_steps}) without [FINAL_ANSWER].")

    def run_trace(self, user_query: str) -> RunTrace:
        """
        Run the agent loop and return the final answer plus a full reasoning trace.

        This is an opt-in debugging/observability API; `run()` remains unchanged.
        """
        self.memory.add(Message(role="user", content=user_query))
        steps: list[StepLog] = []

        for step in range(1, self.config.max_steps + 1):
            prompt = self.build_prompt(user_query=user_query)
            raw = self.llm.generate(prompt, temperature=self.config.temperature)
            self.memory.add(Message(role="assistant", content=raw, metadata={"step": step}))

            blocks = _extract_blocks(raw)
            thought = blocks.get("THOUGHT")
            action_text = blocks.get("ACTION")
            final_text = blocks.get("FINAL_ANSWER")

            if final_text:
                final = final_text.strip()
                steps.append(
                    StepLog(
                        step=step,
                        prompt=prompt,
                        raw_model_output=raw,
                        thought=thought,
                        action=None,
                        observation=None,
                        final_answer=final,
                    )
                )
                self.memory.add(Message(role="assistant", content=final, metadata={"final": True}))
                return RunTrace(final_answer=final, steps=steps)

            if not action_text:
                raise AgentParseError("Model output missing [ACTION] and [FINAL_ANSWER].")

            call = _parse_action(action_text)

            tool_opts = ToolRunOptions(
                timeout_s=self.config.tools.timeout_s,
                max_output_chars=self.config.tools.max_output_chars,
                allow_dangerous_tools=self.config.tools.allow_dangerous_tools,
            )
            result: ToolResult = self.tools.run(call.tool, call.args, options=tool_opts)

            obs_payload = result.to_json()
            obs_text = json.dumps(obs_payload, ensure_ascii=False)
            self.memory.add(
                Message(
                    role="tool",
                    content=f"[OBSERVATION]\n{obs_text}",
                    metadata={"tool": call.tool, "status": result.status.value, "step": step},
                )
            )

            steps.append(
                StepLog(
                    step=step,
                    prompt=prompt,
                    raw_model_output=raw,
                    thought=thought,
                    action={"tool": call.tool, "args": call.args},
                    observation=obs_payload,
                    final_answer=None,
                )
            )

        raise RuntimeError(f"Max steps exceeded ({self.config.max_steps}) without [FINAL_ANSWER].")

