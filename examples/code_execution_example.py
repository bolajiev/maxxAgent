"""
Sandboxed code execution example using `SandboxedPythonExecutor` and the `execute_code` tool.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from maxxa_agent.execution.sandbox import SandboxedPythonExecutor


def main() -> None:
    executor = SandboxedPythonExecutor(workspace_root=".", timeout_s=2.0, max_output_chars=10_000)
    code = "print('hello from sandbox')\nprint(2+2)"
    res = executor.run(code)
    print("ok:", res.ok)
    print("returncode:", res.returncode)
    print("stdout:\n", res.stdout)
    print("stderr:\n", res.stderr)


if __name__ == "__main__":
    main()

