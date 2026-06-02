# API Reference

**Related:** [Architecture](ARCHITECTURE.md) · [Getting Started](GETTING_STARTED.md) · [Advanced Topics](ADVANCED_TOPICS.md)

This reference documents the public API for **MaxxAgentFramework v0.1.0**. Types use Python 3.10+ syntax.

---

## `maxxa_agent.core.agent`

### `Agent`

Main orchestrator for the ReAct loop.

```python
Agent(
    *,
    llm: LLMClient,
    config: AgentConfig | None = None,
    tools: ToolRegistry | None = None,
    memory: ConversationMemory | None = None,
) -> Agent
```

| Method | Returns | Description |
|--------|---------|-------------|
| `build_prompt(user_query: str) -> str` | `str` | Assembles system + memory + user query for the LLM. |
| `run(user_query: str) -> str` | `str` | Runs loop until `[FINAL_ANSWER]` or raises. |
| `run_trace(user_query: str) -> RunTrace` | `RunTrace` | Same as `run`, plus full step trace. |

**Attributes:** `llm`, `config`, `tools`, `memory`

**Example:**

```python
from maxxa_agent.core.agent import Agent
from maxxa_agent.core.config import AgentConfig
from maxxa_agent.core.tools import ToolRegistry
from maxxa_agent.backends.llm_client import CustomEndpointClient

agent = Agent(
    llm=CustomEndpointClient(endpoint_url="http://localhost:8080/generate"),
    config=AgentConfig(max_steps=10),
    tools=ToolRegistry.with_builtins(workspace_root="."),
)
answer = agent.run("Summarize the project README.")
```

### `AgentParseError`

Raised when model output cannot be parsed (missing `[ACTION]` and `[FINAL_ANSWER]`, invalid JSON in `[ACTION]`).

### `ToolCall`

```python
@dataclass(frozen=True)
class ToolCall:
    tool: str
    args: dict[str, Any]
```

Parsed from `[ACTION]` JSON: `{"tool": "name", "args": {...}}`.

### `StepLog` / `RunTrace`

```python
@dataclass(frozen=True)
class StepLog:
    step: int
    prompt: str
    raw_model_output: str
    thought: str | None
    action: dict[str, Any] | None
    observation: dict[str, Any] | None
    final_answer: str | None

@dataclass(frozen=True)
class RunTrace:
    final_answer: str
    steps: list[StepLog]
```

---

## `maxxa_agent.core.tools`

### `ToolSpec`

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_schema: Mapping[str, Any]  # JSON Schema
    handler: Callable[[dict[str, Any]], ToolResult]
    is_dangerous: bool = False
```

### `ToolResult`

```python
@dataclass
class ToolResult:
    result: Any = None
    status: ToolRunStatus = ToolRunStatus.OK
    error: str | None = None
    metadata: MutableMapping[str, Any]
    stdout: str | None = None
    stderr: str | None = None

    def to_json(self) -> dict[str, Any]: ...
```

### `ToolRunStatus`

Enum: `OK`, `ERROR`, `TIMEOUT`, `INVALID_ARGS`, `NOT_FOUND`.

### `ToolRunOptions`

```python
@dataclass
class ToolRunOptions:
    timeout_s: float | None = None
    max_output_chars: int = 50_000
    allow_dangerous_tools: bool = False
```

### `ToolRegistry`

| Method | Description |
|--------|-------------|
| `register(spec: ToolSpec) -> None` | Register a tool (raises if duplicate name). |
| `has(name: str) -> bool` | Check registration. |
| `get(name: str) -> ToolSpec` | Get spec (raises `ToolNotFoundError`). |
| `list_specs() -> list[ToolSpec]` | List all tools. |
| `validate_args(tool_name, args) -> dict` | JSON Schema validation. |
| `run(tool_name, args, *, options=None) -> ToolResult` | Validate and execute. |

**Class method:**

```python
ToolRegistry.with_builtins(
    *,
    workspace_root: str | None = None,
    enable_code_execution: bool = False,
) -> ToolRegistry
```

Registers: `read_url`, `web_search`, `file_ops`, `code_execution`.

### Built-in tool schemas (summary)

| Tool | Required args | Dangerous |
|------|---------------|-----------|
| `read_url` | `url` | No |
| `web_search` | `query` (optional `endpoint_url`) | No |
| `file_ops` | `op`, `path` | Yes |
| `code_execution` | `code` | Yes |

---

## `maxxa_agent.core.memory`

### `Message`

```python
@dataclass(frozen=True)
class Message:
    role: str          # e.g. "user", "assistant", "tool", "system"
    content: str
    timestamp_s: float
    metadata: Mapping[str, Any]
```

### `ConversationMemory`

```python
ConversationMemory(
    *,
    window_size: int = 5,
    summarizer: SummarizerHook | None = None,
    summary_trigger_count: int = 30,
)
```

| Method | Description |
|--------|-------------|
| `add(message: Message) -> None` | Append message; may trigger summarization. |
| `extend(messages) -> None` | Append multiple. |
| `all() -> list[Message]` | Full history copy. |
| `clear() -> None` | Reset memory and summary. |
| `context_messages() -> list[Message]` | Last `window_size` messages. |
| `to_prompt_blocks() -> list[dict[str, str]]` | `{"role", "content"}` for prompting. |

`SummarizerHook = Callable[[Sequence[Message]], str]`

---

## `maxxa_agent.core.config`

### `AgentConfig`

```python
@dataclass(frozen=True)
class AgentConfig:
    backend: BackendConfig = BackendConfig()
    tools: ToolConfig = ToolConfig()
    memory: MemoryConfig = MemoryConfig()
    max_steps: int = 10
    temperature: float = 0.2
    system_prompt: str = "..."  # ReAct format instructions

    def validate(self) -> None: ...
```

### `ToolConfig`

| Field | Default | Description |
|-------|---------|-------------|
| `timeout_s` | `20.0` | Tool timeout (cooperative). |
| `max_output_chars` | `50000` | Truncate tool streams. |
| `allow_dangerous_tools` | `False` | Enable `is_dangerous` tools. |
| `enable_code_execution` | `False` | Builtin `code_execution` flag. |

### `MemoryConfig`

| Field | Default |
|-------|---------|
| `window_size` | `5` |
| `summary_trigger_count` | `30` |

### `BackendConfig`

| Field | Default |
|-------|---------|
| `name` | `"custom"` |
| `options` | `{}` |

Metadata only; does not auto-create clients.

---

## `maxxa_agent.backends.llm_client`

### `LLMClient` (Protocol)

```python
def generate(
    self,
    prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    stop: list[str] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> str: ...
```

### `CustomEndpointClient`

```python
CustomEndpointClient(
    endpoint_url: str,
    request_timeout_s: float = 30.0,
    headers: Mapping[str, str] | None = None,
)
```

POST JSON `{ "prompt", "temperature", ... }`. Accepts response `{ "text" }`, `{ "output" }`, or OpenAI-style `choices[0].text`.

### `HFInferenceClient`

```python
HFInferenceClient(model_id: str, api_token: str, request_timeout_s: float = 30.0)
```

### `OpenAIClient`

```python
OpenAIClient(
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    request_timeout_s: float = 30.0,
)
```

Requires optional dependency: `pip install -e ".[openai]"`.

### `LLMBackendError`

Raised on HTTP/provider failures.

---

## `maxxa_agent.multi_agent`

### `Task`

```python
@dataclass(frozen=True)
class Task:
    description: str
    assigned_agent: str
    task_id: str          # auto UUID if omitted
    created_at_s: float
    context: Any | None
    metadata: Mapping[str, Any]
```

### `TaskResult`

```python
@dataclass
class TaskResult:
    task_id: str
    agent_name: str
    output: str
    success: bool = True
    error: str | None = None
    artifacts: dict[str, Any]
    metadata: dict[str, Any]
```

### `AgentDefinition` / `Crew`

```python
@dataclass(frozen=True)
class AgentDefinition:
    name: str
    role: str
    agent: Agent

class Crew:
    def __init__(self, *, agents: Iterable[AgentDefinition]) -> None: ...
    def list_agents(self) -> list[AgentDefinition]: ...
    def get_agent(self, name: str) -> AgentDefinition: ...
    def run_task(self, task: Task) -> TaskResult: ...
    def enable_delegation_tools(self) -> None: ...
```

`enable_delegation_tools()` registers a `delegate` tool on each agent: `{"agent": "Name", "task": "..."}`.

### `make_agent_definition`

```python
make_agent_definition(
    *,
    name: str,
    role: str,
    base_agent: Agent,
    system_prompt: str | None = None,
) -> AgentDefinition
```

### `Orchestrator`

```python
Orchestrator(*, crew: Crew, aggregator: Aggregator | None = None)
```

| Method | Description |
|--------|-------------|
| `run_sequential(tasks, *, pass_context=True)` | Ordered execution. |
| `run_parallel(tasks, *, max_workers=3)` | Thread pool execution. |
| `run_hierarchical(*, manager_task, subtasks, synthesis_agent=None, max_workers=3)` | Subtasks + synthesis. |
| `run_reactive(initial_tasks, *, policy, max_rounds=5, max_workers=3)` | Dynamic task spawning. |

Returns `OrchestrationResult(results, aggregated_output, mode)`.

`CoordinationMode`: `SEQUENTIAL`, `PARALLEL`, `HIERARCHICAL`, `REACTIVE`.

---

## `maxxa_agent.rag`

### `Document` / `DocumentChunk`

```python
Document(text: str, source: str, metadata: Mapping = {})
DocumentChunk(text: str, source: str, chunk_id: str, metadata: Mapping = {})
```

### `DocumentLoader`

```python
DocumentLoader(*, max_chars: int = 2_000_000)
    .load_text_file(path, *, encoding="utf-8") -> Document
    .load_url(url, *, timeout_s=20.0) -> Document
```

### `TextSplitter`

```python
TextSplitter(*, chunk_size=800, chunk_overlap=100)
    .split(doc: Document, *, prefix_id=None) -> list[DocumentChunk]
```

### `Retriever`

```python
Retriever(*, embedder: Embedder, store: InMemoryVectorStore | None = None)
    .add_chunks(chunks: Sequence[DocumentChunk]) -> None
    .query(query: str, *, top_k=5) -> list[Mapping[str, Any]]
```

Hit shape: `{ score, chunk_id, source, text, metadata }`.

### `LocalHashEmbedder` / `InMemoryVectorStore`

Default deterministic embedder (`dim=256`) and in-memory cosine search.

---

## `maxxa_agent.execution.sandbox`

### `SandboxedPythonExecutor`

```python
SandboxedPythonExecutor(
    *,
    workspace_root: str,
    timeout_s: float = 5.0,
    max_output_chars: int = 50_000,
)
    .run(code: str) -> ExecutionResult
    .install_requirements(requirements_path: str) -> ExecutionResult  # explicit opt-in
```

### `ExecutionResult`

```python
@dataclass
class ExecutionResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    metadata: dict[str, object]
```

---

## `maxxa_agent.tools.advanced_tools`

### `register_advanced_tools`

```python
register_advanced_tools(
    registry: ToolRegistry,
    *,
    workspace_root: str,
    retriever: Retriever | None = None,
    enable_execution: bool = True,
    web_search_endpoint_url: str | None = None,
) -> None
```

| Tool | Notes |
|------|-------|
| `read_file` | Workspace-bounded read |
| `write_file` | Workspace-bounded write |
| `list_files` | Directory listing |
| `execute_code` | Uses `SandboxedPythonExecutor` |
| `web_search` | Rate-limited; requires `web_search_endpoint_url` |
| `query_knowledge_base` | Requires `retriever` |

Individual factories: `read_file_tool`, `write_file_tool`, `list_files_tool`, `execute_code_tool`, `web_search_tool`, `query_knowledge_base_tool`.

---

## Tool name matrix

Use **one** file-tool pack per registry to avoid confusion.

| Capability | Built-in (`core.tools`) | Advanced (`tools.advanced_tools`) |
|------------|-------------------------|-----------------------------------|
| Read file | `file_ops` (`read_text`) | `read_file` |
| Write file | `file_ops` (`write_text`) | `write_file` |
| List dir | `file_ops` (`list_dir`) | `list_files` |
| Run Python | `code_execution` | `execute_code` |
| Web search | `web_search` | `web_search` (rate-limited) |
| RAG query | — | `query_knowledge_base` |
| Fetch URL | `read_url` | — |

---

## Planned APIs (not in v0.1)

See [Roadmap](ROADMAP.md): `MaxxClient`, parser repair helpers, cost tracker, async clients, CLI, persistence serializers.
