"""
Tooling primitives for MaxxAgentFramework.

This module defines:
- `ToolSpec`: a tool definition (name/description/JSON schema/handler)
- `ToolResult`: a structured tool execution result (result + metadata)
- `ToolRegistry`: a registry that validates args and executes tools safely

Design goals:
- Production-grade error handling and metadata (timing, errors, truncation)
- JSON-schema validation for tool arguments (no ad-hoc parsing)
- Safe defaults: timeouts, bounded output, explicit enablement for risky tools
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError


class ToolError(Exception):
    """Base class for tool-related errors."""


class ToolNotFoundError(ToolError):
    """Raised when a tool name is not registered."""


class ToolValidationError(ToolError):
    """Raised when tool arguments fail JSON schema validation."""


class ToolExecutionError(ToolError):
    """Raised when a tool handler raises or returns an invalid result."""


class ToolTimeoutError(ToolError):
    """Raised when tool execution exceeds the configured timeout."""


class ToolRunStatus(str, Enum):
    """High-level outcome of a tool run."""

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    INVALID_ARGS = "invalid_args"
    NOT_FOUND = "not_found"


JsonDict = dict[str, Any]
ToolHandler = Callable[[JsonDict], "ToolResult"]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """
    A tool specification.

    Args:
        name: Tool name. Must be unique within a registry.
        description: Human-readable description for the LLM / user.
        args_schema: JSON schema (Draft 2020-12 compatible) describing arguments.
        handler: Callable that executes the tool. It receives a JSON object
            matching `args_schema` and returns a `ToolResult`.
        is_dangerous: If True, tool execution requires explicit enablement.
    """

    name: str
    description: str
    args_schema: Mapping[str, Any]
    handler: ToolHandler
    is_dangerous: bool = False

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("ToolSpec.name must be a non-empty string.")
        if not self.description or not isinstance(self.description, str):
            raise ValueError("ToolSpec.description must be a non-empty string.")
        if not isinstance(self.args_schema, Mapping):
            raise ValueError("ToolSpec.args_schema must be a mapping.")


@dataclass(slots=True)
class ToolResult:
    """
    Structured tool output.

    `result` should be JSON-serializable for best interoperability.
    """

    result: Any = None
    status: ToolRunStatus = ToolRunStatus.OK
    error: str | None = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    # Optional captured streams (useful for `code_execution`-style tools)
    stdout: str | None = None
    stderr: str | None = None

    def to_json(self) -> JsonDict:
        return {
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "metadata": dict(self.metadata),
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


@dataclass(slots=True)
class ToolRunOptions:
    """Execution options applied at runtime."""

    timeout_s: float | None = None
    max_output_chars: int = 50_000
    allow_dangerous_tools: bool = False


def _truncate_text(text: str | None, max_chars: int) -> tuple[str | None, bool]:
    if text is None:
        return None, False
    if max_chars <= 0:
        return "", True
    if len(text) <= max_chars:
        return text, False
    return text[: max_chars - 1] + "…", True


class ToolRegistry:
    """
    Registers, validates, and executes tools.

    Notes:
    - Arg validation is performed using JSON Schema Draft 2020-12.
    - Timeouts are enforced cooperatively: the registry measures elapsed time
      and can fail fast when a handler returns late, but cannot preempt a
      runaway in-process function. For hard isolation, implement the tool
      handler using a subprocess and enforce a subprocess timeout there.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._validators: dict[str, Draft202012Validator] = {}

    @classmethod
    def with_builtins(
        cls,
        *,
        workspace_root: str | None = None,
        enable_code_execution: bool = False,
    ) -> ToolRegistry:
        """
        Create a registry preloaded with built-in tools.

        Built-ins:
        - `read_url`: fetch a URL and return text
        - `web_search`: lightweight web search via a configurable endpoint (stub-safe)
        - `file_ops`: safe file operations scoped to `workspace_root`
        - `code_execution`: disabled by default; local subprocess execution with strict limits
        """
        reg = cls()
        reg.register(_builtin_read_url())
        reg.register(_builtin_web_search())
        reg.register(_builtin_file_ops(workspace_root=workspace_root))
        reg.register(_builtin_code_execution(enabled=enable_code_execution))
        return reg

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec
        self._validators[spec.name] = Draft202012Validator(dict(spec.args_schema))

    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as e:
            raise ToolNotFoundError(name) from e

    def list_specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def validate_args(self, tool_name: str, args: Any) -> JsonDict:
        if tool_name not in self._tools:
            raise ToolNotFoundError(tool_name)
        if not isinstance(args, dict):
            raise ToolValidationError("Tool args must be a JSON object.")
        validator = self._validators[tool_name]
        try:
            validator.validate(args)
        except JsonSchemaValidationError as e:
            raise ToolValidationError(e.message) from e
        return args

    def run(
        self,
        tool_name: str,
        args: Any,
        *,
        options: ToolRunOptions | None = None,
    ) -> ToolResult:
        """
        Validate and execute a tool.

        Returns a `ToolResult` for both success and failure cases. Exceptions are
        reserved for programmer errors (e.g. invalid registry state).
        """

        opts = options or ToolRunOptions()
        start = time.perf_counter()

        if tool_name not in self._tools:
            return ToolResult(
                status=ToolRunStatus.NOT_FOUND,
                error=f"Tool not found: {tool_name}",
                metadata={"tool": tool_name},
            )

        spec = self._tools[tool_name]
        if spec.is_dangerous and not opts.allow_dangerous_tools:
            return ToolResult(
                status=ToolRunStatus.ERROR,
                error=f"Tool '{tool_name}' is marked dangerous and is disabled.",
                metadata={"tool": tool_name, "is_dangerous": True},
            )

        try:
            validated = self.validate_args(tool_name, args)
        except ToolNotFoundError:
            return ToolResult(
                status=ToolRunStatus.NOT_FOUND,
                error=f"Tool not found: {tool_name}",
                metadata={"tool": tool_name},
            )
        except ToolValidationError as e:
            return ToolResult(
                status=ToolRunStatus.INVALID_ARGS,
                error=str(e),
                metadata={"tool": tool_name},
            )

        try:
            result = spec.handler(validated)
        except Exception as e:  # noqa: BLE001 - tool failures are captured
            elapsed_s = time.perf_counter() - start
            return ToolResult(
                status=ToolRunStatus.ERROR,
                error=f"{type(e).__name__}: {e}",
                metadata={"tool": tool_name, "elapsed_s": elapsed_s},
            )

        if not isinstance(result, ToolResult):
            elapsed_s = time.perf_counter() - start
            return ToolResult(
                status=ToolRunStatus.ERROR,
                error="Tool handler did not return ToolResult.",
                metadata={
                    "tool": tool_name,
                    "elapsed_s": elapsed_s,
                    "returned_type": type(result).__name__,
                },
            )

        elapsed_s = time.perf_counter() - start
        result.metadata.setdefault("tool", tool_name)
        result.metadata.setdefault("elapsed_s", elapsed_s)

        if opts.timeout_s is not None and elapsed_s > opts.timeout_s:
            result.status = ToolRunStatus.TIMEOUT
            result.error = result.error or (
                f"Tool '{tool_name}' exceeded timeout of {opts.timeout_s:.3f}s."
            )

        # Best-effort truncation of captured streams and JSON rendering.
        result.stdout, stdout_trunc = _truncate_text(result.stdout, opts.max_output_chars)
        result.stderr, stderr_trunc = _truncate_text(result.stderr, opts.max_output_chars)
        if stdout_trunc or stderr_trunc:
            result.metadata["output_truncated"] = True

        # Ensure result is JSON-serializable (best effort) to avoid breaking memory/prompt building.
        try:
            json.dumps(result.to_json())
        except TypeError:
            result.metadata["non_json_serializable_result"] = True
            result.result = str(result.result)

        return result


def _builtin_read_url() -> ToolSpec:
    def handler(args: JsonDict) -> ToolResult:
        url = args["url"]
        timeout_s = float(args.get("timeout_s", 20.0))
        max_chars = int(args.get("max_chars", 200_000))
        try:
            with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                text = resp.text
        except Exception as e:  # noqa: BLE001
            return ToolResult(status=ToolRunStatus.ERROR, error=f"{type(e).__name__}: {e}")

        text, truncated = _truncate_text(text, max_chars)
        meta: dict[str, Any] = {"url": url, "truncated": truncated}
        return ToolResult(result={"text": text}, metadata=meta)

    return ToolSpec(
        name="read_url",
        description="Fetch a URL and return response text (best-effort).",
        args_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "minLength": 1},
                "timeout_s": {"type": "number", "minimum": 1, "default": 20.0},
                "max_chars": {"type": "integer", "minimum": 1, "default": 200000},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        handler=handler,
        is_dangerous=False,
    )


def _builtin_web_search() -> ToolSpec:
    """
    Built-in web_search.

    This is intentionally conservative and configurable: by default it requires
    the user to provide a `endpoint_url` for their preferred search service.
    """

    def handler(args: JsonDict) -> ToolResult:
        query = args["query"]
        endpoint_url = args.get("endpoint_url")
        if not endpoint_url:
            return ToolResult(
                status=ToolRunStatus.ERROR,
                error=(
                    "web_search requires 'endpoint_url' pointing to a search service. "
                    "Provide one (e.g. your own proxy) to enable."
                ),
            )
        timeout_s = float(args.get("timeout_s", 20.0))
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.post(endpoint_url, json={"query": query})
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:  # noqa: BLE001
            return ToolResult(status=ToolRunStatus.ERROR, error=f"{type(e).__name__}: {e}")

        return ToolResult(result=data, metadata={"query": query})

    return ToolSpec(
        name="web_search",
        description="Perform a web search via a configured endpoint and return JSON results.",
        args_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "endpoint_url": {"type": "string", "minLength": 1},
                "timeout_s": {"type": "number", "minimum": 1, "default": 20.0},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=handler,
        is_dangerous=False,
    )


def _safe_join(root: str, rel_path: str) -> str:
    root_abs = os.path.abspath(root)
    candidate = os.path.abspath(os.path.join(root_abs, rel_path))
    if os.path.commonpath([root_abs, candidate]) != root_abs:
        raise ValueError("Path escapes workspace root.")
    return candidate


def _builtin_file_ops(*, workspace_root: str | None) -> ToolSpec:
    root = os.path.abspath(workspace_root or os.getcwd())

    def handler(args: JsonDict) -> ToolResult:
        op = args["op"]
        path = args["path"]
        try:
            safe_path = _safe_join(root, path)
        except Exception as e:  # noqa: BLE001
            return ToolResult(status=ToolRunStatus.INVALID_ARGS, error=str(e), metadata={"root": root})

        try:
            if op == "read_text":
                with open(safe_path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
                text, truncated = _truncate_text(text, int(args.get("max_chars", 200_000)))
                return ToolResult(result={"text": text}, metadata={"path": path, "truncated": truncated})

            if op == "write_text":
                content = args["content"]
                os.makedirs(os.path.dirname(safe_path), exist_ok=True)
                with open(safe_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return ToolResult(result={"ok": True}, metadata={"path": path})

            if op == "list_dir":
                entries = sorted(os.listdir(safe_path))
                return ToolResult(result={"entries": entries}, metadata={"path": path})

            return ToolResult(status=ToolRunStatus.INVALID_ARGS, error=f"Unknown op: {op}")
        except Exception as e:  # noqa: BLE001
            return ToolResult(status=ToolRunStatus.ERROR, error=f"{type(e).__name__}: {e}", metadata={"path": path})

    return ToolSpec(
        name="file_ops",
        description="Perform safe file operations scoped to a workspace root.",
        args_schema={
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["read_text", "write_text", "list_dir"]},
                "path": {"type": "string", "minLength": 1},
                "content": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 1, "default": 200000},
            },
            "required": ["op", "path"],
            "additionalProperties": False,
        },
        handler=handler,
        is_dangerous=True,
    )


def _builtin_code_execution(*, enabled: bool) -> ToolSpec:
    def handler(args: JsonDict) -> ToolResult:
        if not enabled:
            return ToolResult(
                status=ToolRunStatus.ERROR,
                error="code_execution is disabled by default. Enable it explicitly in AgentConfig.",
            )

        language = args.get("language", "python")
        code = args["code"]
        timeout_s = float(args.get("timeout_s", 5.0))
        max_chars = int(args.get("max_chars", 50_000))

        if language != "python":
            return ToolResult(status=ToolRunStatus.INVALID_ARGS, error="Only language='python' is supported.")

        # Execute in a separate process to enforce a hard timeout.
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired as e:
            stdout, _ = _truncate_text(e.stdout, max_chars)
            stderr, _ = _truncate_text(e.stderr, max_chars)
            return ToolResult(
                status=ToolRunStatus.TIMEOUT,
                error=f"Execution exceeded timeout of {timeout_s:.3f}s.",
                stdout=stdout,
                stderr=stderr,
                metadata={"timeout_s": timeout_s},
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(status=ToolRunStatus.ERROR, error=f"{type(e).__name__}: {e}")

        stdout, stdout_trunc = _truncate_text(proc.stdout, max_chars)
        stderr, stderr_trunc = _truncate_text(proc.stderr, max_chars)
        meta: dict[str, Any] = {
            "returncode": proc.returncode,
            "stdout_truncated": stdout_trunc,
            "stderr_truncated": stderr_trunc,
        }
        status = ToolRunStatus.OK if proc.returncode == 0 else ToolRunStatus.ERROR
        err = None if proc.returncode == 0 else f"Non-zero return code: {proc.returncode}"
        return ToolResult(status=status, error=err, stdout=stdout, stderr=stderr, metadata=meta)

    return ToolSpec(
        name="code_execution",
        description="Execute small snippets of code (disabled by default).",
        args_schema={
            "type": "object",
            "properties": {
                "language": {"type": "string", "default": "python"},
                "code": {"type": "string", "minLength": 1},
                "timeout_s": {"type": "number", "minimum": 0.1, "default": 5.0},
                "max_chars": {"type": "integer", "minimum": 1, "default": 50000},
            },
            "required": ["code"],
            "additionalProperties": False,
        },
        handler=handler,
        is_dangerous=True,
    )

