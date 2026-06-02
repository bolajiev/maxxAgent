# Examples

**Related:** [Getting Started](GETTING_STARTED.md) · [Advanced Topics](ADVANCED_TOPICS.md) · [Troubleshooting](TROUBLESHOOTING.md)

All examples live under `examples/`. From the repo root, either install the package (`pip install -e .`) or rely on the built-in `sys.path` bootstrap in each script.

## Catalog

| Script | What it demonstrates | Requirements |
|--------|----------------------|--------------|
| [multi_agent_example.py](../examples/multi_agent_example.py) | `Crew`, `Orchestrator.run_sequential`, three roles (Researcher/Coder/Reviewer) | None (scripted LLM) |
| [rag_example.py](../examples/rag_example.py) | `TextSplitter`, `Retriever`, `LocalHashEmbedder` | None |
| [code_execution_example.py](../examples/code_execution_example.py) | `SandboxedPythonExecutor` | None |

## multi_agent_example.py

**Run:**

```bash
python examples/multi_agent_example.py
```

**Shows:**

- Multiple `AgentDefinition` instances with role-specific system prompts
- Sequential orchestration passing context between tasks
- `ScriptedLLM` — deterministic backend that emits valid `[FINAL_ANSWER]` blocks

**Extend it:**

- Replace `ScriptedLLM` with `CustomEndpointClient` pointing at your Maxx server
- Add `crew.enable_delegation_tools()` and teach the manager agent to call `delegate`
- Switch to `orchestrator.run_parallel` for independent subtasks

## rag_example.py

**Run:**

```bash
python examples/rag_example.py
```

**Shows:**

- In-memory documents → chunks → embeddings → semantic query
- Hit format: `score`, `source`, `chunk_id`, `text`

**Extend it:**

- Load real files: `DocumentLoader().load_text_file("docs/ARCHITECTURE.md")`
- Register `query_knowledge_base` on an `Agent` via `register_advanced_tools`
- Swap `LocalHashEmbedder` for a production embedder implementing `Embedder`

## code_execution_example.py

**Run:**

```bash
python examples/code_execution_example.py
```

**Shows:**

- Direct use of `SandboxedPythonExecutor` (bypassing the agent loop)
- stdout/stderr capture and return codes

**Extend it:**

- Register `execute_code` on a `ToolRegistry` with `allow_dangerous_tools=True`
- Use a dedicated `./workspace` directory as `workspace_root`
- Add `install_requirements("requirements.txt")` for dependency installs (explicit, not automatic)

## Planned example (not yet in repo)

**`demo_full_agent.py`** (Roadmap Phase 1) — single end-to-end flow:

1. Build RAG index from project docs
2. Create agent with advanced tools + retriever
3. Run `run_trace()` on a user question
4. Print final answer and step timeline

Track progress in [Roadmap](ROADMAP.md).

## Running from source without install

Examples prepend the repo root to `sys.path`. For library use in other projects, prefer:

```bash
pip install -e .
```
