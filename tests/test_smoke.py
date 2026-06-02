"""Smoke tests for MaxxAgentFramework."""

from __future__ import annotations

import subprocess
import sys

import pytest

from maxxa_agent.core.tools import ToolRegistry, ToolResult, ToolSpec, ToolRunStatus
from maxxa_agent.execution.sandbox import SandboxedPythonExecutor
from maxxa_agent.rag.loader import Document, TextSplitter
from maxxa_agent.rag.retriever import LocalHashEmbedder, Retriever


def test_package_version() -> None:
    import maxxa_agent

    assert maxxa_agent.__version__ == "0.1.0"


def test_tool_registry_custom_tool() -> None:
    def echo(args: dict) -> ToolResult:
        return ToolResult(result={"echo": args["msg"]})

    reg = ToolRegistry()
    reg.register(
        ToolSpec(
            name="echo",
            description="Echo a message.",
            args_schema={
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": ["msg"],
                "additionalProperties": False,
            },
            handler=echo,
        )
    )
    out = reg.run("echo", {"msg": "hi"})
    assert out.status == ToolRunStatus.OK
    assert out.result == {"echo": "hi"}


def test_retriever_query() -> None:
    doc = Document(text="ReAct uses THOUGHT ACTION OBSERVATION tags.", source="test")
    chunks = TextSplitter(chunk_size=100, chunk_overlap=10).split(doc)
    retriever = Retriever(embedder=LocalHashEmbedder(dim=64))
    retriever.add_chunks(chunks)
    hits = retriever.query("ReAct tags", top_k=1)
    assert len(hits) >= 1
    assert "text" in hits[0]


def test_sandbox_executor() -> None:
    ex = SandboxedPythonExecutor(workspace_root=".", timeout_s=5.0)
    res = ex.run("print(42)")
    assert res.ok
    assert "42" in res.stdout


@pytest.mark.parametrize(
    "script",
    [
        "examples/multi_agent_example.py",
        "examples/rag_example.py",
        "examples/code_execution_example.py",
    ],
)
def test_example_scripts(script: str) -> None:
    proc = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
