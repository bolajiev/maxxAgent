"""
Sandboxed Python execution (OpenDevin-style building block).

Security note:
- A fully hardened sandbox is OS- and container-dependent.
- This implementation provides *practical* safety defaults:
  - subprocess isolation
  - hard timeout
  - bounded stdout/stderr
  - restricted working directory (workspace root)
  - optional requirements installation hook (off by default)

For stronger isolation, run this inside a container (Docker) or a restricted VM.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class ExecutionResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    metadata: dict[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


def _truncate(text: Optional[str], max_chars: int) -> tuple[str, bool]:
    t = text or ""
    if max_chars <= 0:
        return "", True
    if len(t) <= max_chars:
        return t, False
    return t[: max_chars - 1] + "…", True


class SandboxedPythonExecutor:
    """
    Executes Python code with workspace scoping and timeouts.

    Args:
        workspace_root: Root directory for execution (cwd). File access is not
            technically prevented by Python itself, but tooling should combine
            this with safe file tools for a bounded interface.
        timeout_s: Hard timeout for execution.
        max_output_chars: Truncate stdout/stderr to this size.
    """

    def __init__(
        self,
        *,
        workspace_root: str,
        timeout_s: float = 5.0,
        max_output_chars: int = 50_000,
    ) -> None:
        self.workspace_root = str(Path(workspace_root).resolve())
        self.timeout_s = timeout_s
        self.max_output_chars = max_output_chars

    def run(self, code: str) -> ExecutionResult:
        os.makedirs(self.workspace_root, exist_ok=True)
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", code],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            stdout, _ = _truncate(e.stdout, self.max_output_chars)
            stderr, _ = _truncate(e.stderr, self.max_output_chars)
            return ExecutionResult(
                ok=False,
                returncode=-1,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                metadata={"timeout_s": self.timeout_s},
            )
        except Exception as e:  # noqa: BLE001
            return ExecutionResult(
                ok=False,
                returncode=-1,
                stdout="",
                stderr=f"{type(e).__name__}: {e}",
                timed_out=False,
                metadata={},
            )

        stdout, out_trunc = _truncate(proc.stdout, self.max_output_chars)
        stderr, err_trunc = _truncate(proc.stderr, self.max_output_chars)
        ok = proc.returncode == 0
        meta = {"stdout_truncated": out_trunc, "stderr_truncated": err_trunc}
        return ExecutionResult(ok=ok, returncode=proc.returncode, stdout=stdout, stderr=stderr, metadata=meta)

    def install_requirements(self, requirements_path: str) -> ExecutionResult:
        """
        Optional dependency management hook.

        This uses pip in a subprocess. It is intentionally not enabled as a tool
        by default; call it explicitly if you want this behavior.
        """
        req_abs = str(Path(self.workspace_root, requirements_path).resolve())
        if not req_abs.startswith(self.workspace_root):
            return ExecutionResult(ok=False, returncode=-1, stdout="", stderr="requirements path escapes workspace")

        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", req_abs],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=max(self.timeout_s, 60.0),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except Exception as e:  # noqa: BLE001
            return ExecutionResult(ok=False, returncode=-1, stdout="", stderr=f"{type(e).__name__}: {e}")

        stdout, _ = _truncate(proc.stdout, self.max_output_chars)
        stderr, _ = _truncate(proc.stderr, self.max_output_chars)
        return ExecutionResult(ok=proc.returncode == 0, returncode=proc.returncode, stdout=stdout, stderr=stderr)

