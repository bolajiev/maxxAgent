"""
Memory management for MaxxAgentFramework.

This module provides a conversation memory store with:
- structured messages (role/content/metadata/timestamps)
- a configurable context window (keep last N messages for prompting)
- an optional summarization hook to compress long conversations
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

Role = str  # e.g. "system", "user", "assistant", "tool"


@dataclass(frozen=True, slots=True)
class Message:
    """A single message stored in memory."""

    role: Role
    content: str
    timestamp_s: float = field(default_factory=lambda: time.time())
    metadata: Mapping[str, Any] = field(default_factory=dict)


SummarizerHook = Callable[[Sequence[Message]], str]


class ConversationMemory:
    """
    Stores conversation messages and exposes a prompt-ready context view.

    Args:
        window_size: Number of most recent messages to include when building
            prompt context. Default is 5.
        summarizer: Optional callable that can summarize older messages when
            the conversation grows. If provided, the memory can maintain a
            rolling summary string.
        summary_trigger_count: Minimum total message count before summarization
            is eligible to run.
    """

    def __init__(
        self,
        *,
        window_size: int = 5,
        summarizer: SummarizerHook | None = None,
        summary_trigger_count: int = 30,
    ) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be > 0")
        if summary_trigger_count <= 0:
            raise ValueError("summary_trigger_count must be > 0")
        self._window_size = window_size
        self._messages: list[Message] = []
        self._summarizer = summarizer
        self._summary_trigger_count = summary_trigger_count
        self._summary: str | None = None
        self._last_summarized_index: int = 0

    @property
    def window_size(self) -> int:
        return self._window_size

    @property
    def summary(self) -> str | None:
        return self._summary

    def set_summarizer(self, summarizer: SummarizerHook | None) -> None:
        self._summarizer = summarizer

    def add(self, message: Message) -> None:
        self._messages.append(message)
        self._maybe_summarize()

    def extend(self, messages: Iterable[Message]) -> None:
        for m in messages:
            self._messages.append(m)
        self._maybe_summarize()

    def all(self) -> list[Message]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()
        self._summary = None
        self._last_summarized_index = 0

    def context_messages(self) -> list[Message]:
        """Return the last N messages for prompt context."""
        return self._messages[-self._window_size :]

    def to_prompt_blocks(self) -> list[dict[str, str]]:
        """
        Convert memory to prompt blocks that are safe to serialize.

        Returns blocks like: {"role": "...", "content": "..."}.
        If a summary exists, it is included as an initial system block.
        """
        blocks: list[dict[str, str]] = []
        if self._summary:
            blocks.append(
                {
                    "role": "system",
                    "content": f"[SUMMARY]\n{self._summary}",
                }
            )
        for msg in self.context_messages():
            blocks.append({"role": msg.role, "content": msg.content})
        return blocks

    def _maybe_summarize(self) -> None:
        if self._summarizer is None:
            return
        if len(self._messages) < self._summary_trigger_count:
            return

        # Summarize everything except the current window; only summarize new material since last run.
        cutoff = max(0, len(self._messages) - self._window_size)
        if cutoff <= self._last_summarized_index:
            return

        slice_to_summarize = self._messages[self._last_summarized_index : cutoff]
        if not slice_to_summarize:
            return

        new_summary = self._summarizer(slice_to_summarize)
        if not isinstance(new_summary, str):
            raise TypeError("summarizer must return a string")

        if self._summary:
            self._summary = self._summary.rstrip() + "\n" + new_summary.strip()
        else:
            self._summary = new_summary.strip()

        self._last_summarized_index = cutoff

