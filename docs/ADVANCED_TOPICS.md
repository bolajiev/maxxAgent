# Advanced Topics

**Related:** [Architecture](ARCHITECTURE.md) · [API Reference](API_REFERENCE.md) · [Security](SECURITY.md)

## Multi-agent crews

**Implemented:** coordinate specialized agents with `Crew` and `Orchestrator`.

### Define agents

Each agent is a core `Agent` with its own tools, memory, and system prompt:

```python
from maxx_agent.core.agent import Agent
from maxx_agent.multi_agent.crew import AgentDefinition, Crew
from maxx_agent.multi_agent.orchestrator import Orchestrator
from maxx_agent.multi_agent.task import Task

researcher = AgentDefinition(
    name="Researcher",
    role="Research and summarize",
    agent=Agent(llm=llm, config=researcher_config, tools=research_tools),
)

crew = Crew(agents=[researcher, coder, reviewer])
orchestrator = Orchestrator(crew=crew)

tasks = [
    Task(description="Research safe tool patterns.", assigned_agent="Researcher"),
    Task(description="Draft implementation steps.", assigned_agent="Coder"),
]
result = orchestrator.run_sequential(tasks, pass_context=True)
print(result.aggregated_output)
```

### Coordination patterns

| Method | Pattern |
|--------|---------|
| `run_sequential` | Pipeline with optional `prior_results` in context |
| `run_parallel` | Concurrent tasks, merged by aggregator |
| `run_hierarchical` | Subtasks + manager synthesis |
| `run_reactive` | Policy returns new tasks from each result |

### Delegation

**Implemented:** `crew.enable_delegation_tools()` adds a `delegate` tool to each agent:

```json
{"tool": "delegate", "args": {"agent": "Coder", "task": "Write a function stub for X"}}
```

**Planned:** full manager loop that automatically runs delegate calls and feeds results back (see [Roadmap](ROADMAP.md)).

### Structured handoffs

**Planned:** agents return JSON handoff payloads (`summary`, `decisions`, `artifacts`) for deterministic merging. Today, orchestrators aggregate plain text via `default_aggregator`.

---

## RAG integration

**Implemented:** load → split → embed → retrieve. **Partial:** agent must call `query_knowledge_base` or you pre-fetch context.

### Build an index

```python
from maxx_agent.rag.loader import Document, DocumentLoader, TextSplitter
from maxx_agent.rag.retriever import LocalHashEmbedder, Retriever

loader = DocumentLoader()
doc = loader.load_text_file("README.md")
chunks = TextSplitter(chunk_size=500, chunk_overlap=50).split(doc)

retriever = Retriever(embedder=LocalHashEmbedder(dim=256))
retriever.add_chunks(chunks)
```

### Wire into tools

```python
from maxx_agent.core.tools import ToolRegistry
from maxx_agent.tools.advanced_tools import register_advanced_tools

registry = ToolRegistry()
register_advanced_tools(
    registry,
    workspace_root=".",
    retriever=retriever,
    enable_execution=False,
)

agent = Agent(llm=llm, tools=registry)
```

The model can then use:

```json
{"tool": "query_knowledge_base", "args": {"query": "installation steps", "top_k": 3}}
```

### Pre-fetch pattern (recommended integration)

**Not built into `Agent` by default.** Before `run()`, inject retrieved context:

```python
hits = retriever.query(user_query, top_k=5)
context = "\n\n".join(h["text"] for h in hits)
augmented_query = f"Use this context:\n{context}\n\nQuestion: {user_query}"
answer = agent.run(augmented_query)
```

For production, use a real embedding API (OpenAI, HF, local model) by implementing the `Embedder` protocol.

**Planned:** persistent vector store, database loaders — [Roadmap](ROADMAP.md).

---

## Code execution and sandboxing

**Implemented:** `SandboxedPythonExecutor` and `execute_code` / `code_execution` tools.

```python
from maxx_agent.execution.sandbox import SandboxedPythonExecutor

executor = SandboxedPythonExecutor(workspace_root="./workspace", timeout_s=5.0)
result = executor.run("print(sum(range(10)))")
print(result.stdout)
```

### What is safe

- Subprocess isolation (`python -I -c`)
- Hard timeout
- Bounded stdout/stderr
- Working directory set to workspace root

### What is not safe

- Not a container: code can still access network, env vars, and potentially escape via Python/stdlib depending on OS policy
- File tools + execution together increase risk — scope `workspace_root` narrowly

Enable dangerous tools only when needed:

```python
from maxx_agent.core.config import AgentConfig, ToolConfig

config = AgentConfig(
    tools=ToolConfig(
        allow_dangerous_tools=True,
        enable_code_execution=True,
    ),
)
```

See [Security](SECURITY.md).

**Planned:** Docker-based sandbox — [Roadmap](ROADMAP.md).

---

## Custom tool development

### Patterns

1. **Pure function** — validate args via schema; return `ToolResult`.
2. **Side effects** — mark `is_dangerous=True`; document required config flags.
3. **Delegation** — call other services; enforce timeouts inside handler or use subprocess.

### Example: HTTP fetch tool

```python
import httpx
from maxx_agent.core.tools import ToolSpec, ToolResult, ToolRunStatus

def fetch_json(args: dict) -> ToolResult:
    url = args["url"]
    try:
        r = httpx.get(url, timeout=10.0)
        r.raise_for_status()
        return ToolResult(result=r.json())
    except Exception as e:
        return ToolResult(status=ToolRunStatus.ERROR, error=str(e))

ToolSpec(
    name="fetch_json",
    description="GET a URL and return JSON.",
    args_schema={
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
        "additionalProperties": False,
    },
    handler=fetch_json,
)
```

### Safety checklist

- JSON Schema with `additionalProperties: false`
- Bounded reads/writes
- No shell=True
- Clear errors in `ToolResult.error`

---

## Parser resilience

**Planned for v0.1+** — not shipped in core yet.

Real models often omit tags or emit malformed JSON. Recommended pattern until built-in repair lands:

1. Catch `AgentParseError`.
2. Re-prompt with: “Your last response was invalid. Use exactly [THOUGHT], [ACTION] or [FINAL_ANSWER].”
3. Retry up to N times.
4. Fall back to `run_trace()` logging for debugging.

Alternatively, fine-tune or instruct your Maxx model on the tag format in `AgentConfig.system_prompt`.

---

## Cost tracking

**Planned** — hook points:

- Wrap `LLMClient.generate` to record latency, prompt length, and provider-reported token usage (`extra` dict).
- Attach costs to `StepLog.metadata` in a custom wrapper or future `CostTracker` class.

For paid APIs (OpenAI, HF), track usage at the HTTP client layer and export metrics to your observability stack.

---

## Async support

**Planned (v0.2).** Current API is synchronous. For concurrent tool I/O, use `Orchestrator.run_parallel` at the crew level, not inside a single agent step.
