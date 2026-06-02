# FAQ

**Related:** [Getting Started](GETTING_STARTED.md) · [Roadmap](ROADMAP.md) · [FAQ vs Security](SECURITY.md)

## Why MaxxAgentFramework vs CrewAI, LangGraph, AutoGen, etc.?

MaxxAgentFramework is a **lighter, explicit** Python framework:

- **Transparent ReAct loop** — tagged `[THOUGHT]` / `[ACTION]` / `[FINAL_ANSWER]` format you control
- **Minimal dependencies** — `httpx` + `jsonschema` for core
- **First-class tool safety** — JSON Schema validation, dangerous-tool gates, bounded I/O
- **Modular packages** — core, backends, multi-agent, RAG, execution without a heavy runtime

CrewAI and LangGraph excel at graph orchestration and large ecosystems. MaxxAgentFramework targets integrators who want readable control flow and a clear path to plug in **custom models** (e.g. Maxx).

## Can I use my own model?

**Yes.** Implement or use `CustomEndpointClient` with any HTTP server that accepts a prompt and returns text.

```python
from maxx_agent.backends.llm_client import CustomEndpointClient

llm = CustomEndpointClient(endpoint_url="http://your-maxx-server/generate")
```

Any object with `generate(prompt, *, temperature=..., ...) -> str` works as `LLMClient`.

## How do I add my own tools?

Register a `ToolSpec` on `ToolRegistry`. See [Getting Started — custom tools](GETTING_STARTED.md#2-adding-custom-tools-5-min) and [Development](DEVELOPMENT.md#adding-a-new-tool).

## Is it production-ready?

**Not yet.** v0.1 is a **framework preview**:

- No automated test suite in CI
- Strict tag parsing without built-in repair
- Subprocess sandbox, not container isolation
- In-memory RAG only

Suitable for development, demos, and building on top of. See [Roadmap](ROADMAP.md) for v1.0 goals.

## How fast is it?

**Framework overhead is small** (prompt assembly, JSON validation, memory append). End-to-end latency is dominated by your LLM and tool I/O (HTTP, files, subprocess).

Use `Orchestrator.run_parallel` for independent multi-agent tasks.

## Can I use it offline?

**Partially.**

- Examples with `ScriptedLLM` run fully offline
- `LocalHashEmbedder` RAG demo runs offline
- `SandboxedPythonExecutor` runs offline
- Real agent answers require your local or remote model server

## Does it support streaming?

**Not in v0.1.** `LLMClient.generate` returns a complete string. Streaming is on the [Roadmap](ROADMAP.md).

## How does memory work?

`ConversationMemory` stores all messages but only the last **N** (default 5) appear in prompts. Optional summarizer compresses older history. Not persisted to disk in v0.1.

## Can agents share one tool registry?

You can pass the same `ToolRegistry` instance to multiple `Agent` objects. Be careful with shared mutable state inside tool handlers.

## What's the difference between builtin and advanced file tools?

Builtins use `file_ops` (`read_text`, `write_text`, `list_dir`). Advanced tools use `read_file`, `write_file`, `list_files`. Pick one pack per agent to avoid duplicate names. See [API Reference — tool matrix](API_REFERENCE.md#tool-name-matrix).

## How do I debug a run?

Use `agent.run_trace(query)` and inspect `RunTrace.steps`. See [Troubleshooting](TROUBLESHOOTING.md).

## What license is the project under?

MIT — see [LICENSE](../LICENSE).

## Where is the full documentation?

Start at [docs/README.md](README.md).
