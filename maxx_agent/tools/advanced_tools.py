"""
Advanced tool pack: bounded file ops, sandboxed execution, rate-limited web search, and RAG querying.

These tools are intended to be registered into a `ToolRegistry`.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from maxx_agent.core.tools import ToolRegistry, ToolResult, ToolRunStatus, ToolSpec
from maxx_agent.execution.sandbox import SandboxedPythonExecutor
from maxx_agent.rag.retriever import Retriever


def _safe_join(root: str, rel: str) -> str:
    root_abs = os.path.abspath(root)
    cand = os.path.abspath(os.path.join(root_abs, rel))
    if os.path.commonpath([root_abs, cand]) != root_abs:
        raise ValueError("Path escapes workspace root.")
    return cand


def read_file_tool(*, workspace_root: str, max_chars: int = 200_000) -> ToolSpec:
    def handler(args: dict[str, Any]) -> ToolResult:
        path = args["path"]
        try:
            safe = _safe_join(workspace_root, path)
            with open(safe, encoding="utf-8", errors="replace") as f:
                txt = f.read(max_chars + 1)
            truncated = len(txt) > max_chars
            if truncated:
                txt = txt[: max_chars - 1] + "…"
            return ToolResult(result={"text": txt}, metadata={"path": path, "truncated": truncated})
        except Exception as e:  # noqa: BLE001
            return ToolResult(status=ToolRunStatus.ERROR, error=f"{type(e).__name__}: {e}")

    return ToolSpec(
        name="read_file",
        description="Read a UTF-8 text file from the workspace (bounded).",
        args_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1}},
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=handler,
        is_dangerous=True,
    )


def write_file_tool(*, workspace_root: str, max_chars: int = 1_000_000) -> ToolSpec:
    def handler(args: dict[str, Any]) -> ToolResult:
        path = args["path"]
        content = args["content"]
        if not isinstance(content, str) or len(content) > max_chars:
            return ToolResult(status=ToolRunStatus.INVALID_ARGS, error="content too large or invalid.")
        try:
            safe = _safe_join(workspace_root, path)
            os.makedirs(os.path.dirname(safe), exist_ok=True)
            with open(safe, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(result={"ok": True}, metadata={"path": path})
        except Exception as e:  # noqa: BLE001
            return ToolResult(status=ToolRunStatus.ERROR, error=f"{type(e).__name__}: {e}")

    return ToolSpec(
        name="write_file",
        description="Write a UTF-8 text file inside the workspace (bounded).",
        args_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1}, "content": {"type": "string"}},
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        handler=handler,
        is_dangerous=True,
    )


def list_files_tool(*, workspace_root: str, max_entries: int = 2000) -> ToolSpec:
    def handler(args: dict[str, Any]) -> ToolResult:
        rel = args.get("path", ".")
        try:
            safe = _safe_join(workspace_root, rel)
            entries = []
            for name in os.listdir(safe):
                entries.append(name)
                if len(entries) >= max_entries:
                    break
            entries.sort()
            return ToolResult(
                result={"entries": entries},
                metadata={"path": rel, "truncated": len(entries) >= max_entries},
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(status=ToolRunStatus.ERROR, error=f"{type(e).__name__}: {e}")

    return ToolSpec(
        name="list_files",
        description="List directory entries inside the workspace (bounded).",
        args_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        handler=handler,
        is_dangerous=True,
    )


def execute_code_tool(*, executor: SandboxedPythonExecutor) -> ToolSpec:
    def handler(args: dict[str, Any]) -> ToolResult:
        code = args["code"]
        res = executor.run(code)
        status = ToolRunStatus.OK if res.ok else (ToolRunStatus.TIMEOUT if res.timed_out else ToolRunStatus.ERROR)
        return ToolResult(
            status=status,
            error=None if res.ok else ("timed out" if res.timed_out else "execution failed"),
            result={"returncode": res.returncode},
            stdout=res.stdout,
            stderr=res.stderr,
            metadata=res.metadata,
        )

    return ToolSpec(
        name="execute_code",
        description="Execute Python code in a subprocess sandbox (timeout, bounded output).",
        args_schema={
            "type": "object",
            "properties": {"code": {"type": "string", "minLength": 1}},
            "required": ["code"],
            "additionalProperties": False,
        },
        handler=handler,
        is_dangerous=True,
    )


@dataclass(slots=True)
class TokenBucket:
    rate_per_minute: int
    burst: int
    tokens: float = 0.0
    last_s: float = 0.0

    def allow(self) -> bool:
        now = time.time()
        if self.last_s == 0.0:
            self.last_s = now
            self.tokens = float(self.burst)
        elapsed = max(0.0, now - self.last_s)
        self.last_s = now
        self.tokens = min(float(self.burst), self.tokens + elapsed * (self.rate_per_minute / 60.0))
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


def web_search_tool(*, endpoint_url: str, rate_limit_per_minute: int = 30, burst: int = 5) -> ToolSpec:
    bucket = TokenBucket(rate_per_minute=rate_limit_per_minute, burst=burst)

    def handler(args: dict[str, Any]) -> ToolResult:
        if not bucket.allow():
            return ToolResult(status=ToolRunStatus.ERROR, error="rate limited")
        q = args["query"]
        timeout_s = float(args.get("timeout_s", 20.0))
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.post(endpoint_url, json={"query": q})
                resp.raise_for_status()
                data = resp.json()
            return ToolResult(result=data, metadata={"query": q})
        except Exception as e:  # noqa: BLE001
            return ToolResult(status=ToolRunStatus.ERROR, error=f"{type(e).__name__}: {e}")

    return ToolSpec(
        name="web_search",
        description="Rate-limited web search via configured endpoint (returns JSON).",
        args_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 1}, "timeout_s": {"type": "number", "minimum": 1}},
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=handler,
        is_dangerous=False,
    )


def query_knowledge_base_tool(*, retriever: Retriever) -> ToolSpec:
    def handler(args: dict[str, Any]) -> ToolResult:
        query = args["query"]
        top_k = int(args.get("top_k", 5))
        hits = retriever.query(query, top_k=top_k)
        return ToolResult(result={"hits": hits}, metadata={"query": query, "top_k": top_k})

    return ToolSpec(
        name="query_knowledge_base",
        description="Semantic search over the agent's knowledge base (RAG).",
        args_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=handler,
        is_dangerous=False,
    )


def register_advanced_tools(
    registry: ToolRegistry,
    *,
    workspace_root: str,
    retriever: Retriever | None = None,
    enable_execution: bool = True,
    web_search_endpoint_url: str | None = None,
) -> None:
    """
    Register advanced tools into a registry.

    - File tools are marked dangerous.
    - `execute_code` is marked dangerous and can be disabled.
    - `web_search` requires an explicit endpoint URL.
    - `query_knowledge_base` requires a Retriever.
    """
    registry.register(read_file_tool(workspace_root=workspace_root))
    registry.register(write_file_tool(workspace_root=workspace_root))
    registry.register(list_files_tool(workspace_root=workspace_root))

    if enable_execution:
        executor = SandboxedPythonExecutor(workspace_root=workspace_root)
        registry.register(execute_code_tool(executor=executor))

    if web_search_endpoint_url:
        registry.register(web_search_tool(endpoint_url=web_search_endpoint_url))

    if retriever is not None:
        registry.register(query_knowledge_base_tool(retriever=retriever))

