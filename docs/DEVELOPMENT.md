# Development Guide

**Related:** [Roadmap](ROADMAP.md) · [API Reference](API_REFERENCE.md) · [Quality Metrics](QUALITY_METRICS.md)

## Setting up the development environment

```bash
git clone https://github.com/bolajiev/maxxAgent.git
cd maxxAgent

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e ".[openai]"
```

Dependencies (runtime): `httpx`, `jsonschema` (see [pyproject.toml](../pyproject.toml)).

## Environment variables

Copy the template and keep secrets out of git:

```bash
cp .env.example .env   # macOS/Linux
copy .env.example .env # Windows
```

Edit `.env` with your Maxx endpoint URL, API keys, and tool flags. See [.env.example](../.env.example) for all supported variable names.

Use the settings helper (reads the same variable names as `.env.example`):

```python
from maxx_agent.settings import load_env_file, llm_endpoint_url

load_env_file()  # requires: pip install python-dotenv
print(llm_endpoint_url())
```

Or read `os.environ` directly. See [maxx_agent/settings.py](../maxx_agent/settings.py).

## Running examples

From the repository root:

```bash
python examples/multi_agent_example.py
python examples/rag_example.py
python examples/code_execution_example.py
```

Or after editable install:

```bash
pip install -e .
```

## Running tests

**Planned** — test suite not yet in the repository.

When added, the expected layout:

```text
tests/
├── test_agent.py
├── test_tools.py
├── test_memory.py
├── test_retriever.py
└── test_sandbox.py
```

Expected commands:

```bash
pip install pytest pytest-cov
pytest
pytest --cov=maxx_agent --cov-report=term-missing
```

Until tests exist, validate manually by running all examples.

## Adding a new tool

1. **Define the handler** — accept `dict[str, Any]`, return `ToolResult`.

```python
from maxx_agent.core.tools import ToolResult, ToolRunStatus

def my_tool(args: dict) -> ToolResult:
    try:
        # work here
        return ToolResult(result={"ok": True})
    except Exception as e:
        return ToolResult(status=ToolRunStatus.ERROR, error=str(e))
```

2. **Define JSON Schema** for `args` with `additionalProperties: false`.

3. **Create `ToolSpec`** and register:

```python
from maxx_agent.core.tools import ToolSpec, ToolRegistry

registry.register(
    ToolSpec(
        name="my_tool",
        description="What the model needs to know.",
        args_schema={...},
        handler=my_tool,
        is_dangerous=False,
    )
)
```

4. **Update docs** — [API_REFERENCE.md](API_REFERENCE.md) and [EXAMPLES.md](EXAMPLES.md) if user-facing.

5. **Add tests** when pytest is available.

See [Advanced Topics — Custom tools](ADVANCED_TOPICS.md#custom-tool-development).

## Adding a new LLM backend

Implement the `LLMClient` protocol:

```python
class MyBackend:
    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        extra: dict | None = None,
    ) -> str:
        # call your API
        return generated_text
```

Pass an instance to `Agent(llm=MyBackend())`.

Document request/response format in [API_REFERENCE.md](API_REFERENCE.md).

Reference implementations: [`maxx_agent/backends/llm_client.py`](../maxx_agent/backends/llm_client.py).

## Code style

**Recommended (not yet enforced in repo):**

| Tool | Purpose |
|------|---------|
| [black](https://github.com/psf/black) | Formatting |
| [isort](https://github.com/PyCQA/isort) | Import sorting |
| [mypy](https://mypy-lang.org/) | Type checking |

```bash
pip install black isort mypy
black maxx_agent examples
isort maxx_agent examples
mypy maxx_agent
```

Conventions:

- Python 3.10+ type hints on public APIs
- Docstrings on public classes and methods
- Prefer `ToolResult` over raising in tool handlers

## Pull request process

1. Fork / branch from `main`
2. Keep changes focused
3. Update documentation for API changes
4. Run examples locally
5. Describe behavior change in PR body
6. Link related roadmap item if applicable

## Release checklist

- [ ] Version bump in `pyproject.toml` and `maxx_agent/__init__.py`
- [ ] README and docs reviewed
- [ ] Examples run clean
- [ ] LICENSE unchanged unless intentionally updated
- [ ] Roadmap items marked Done where applicable
- [ ] Tag release in git

## Documentation policy

Keep docs in sync with code:

| Change | Update |
|--------|--------|
| Public API | [API_REFERENCE.md](API_REFERENCE.md) |
| Behavior / architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| New example script | [EXAMPLES.md](EXAMPLES.md) |
| Shipped roadmap item | [ROADMAP.md](ROADMAP.md) |
| Security behavior | [SECURITY.md](SECURITY.md) |

## Project layout

```text
maxx_agent/
  core/          # Agent, tools, memory, config
  backends/      # LLM clients
  multi_agent/   # Crew, Task, Orchestrator
  rag/           # Loader, retriever
  execution/     # SandboxedPythonExecutor
  tools/         # advanced_tools
examples/        # Runnable demos
docs/            # Documentation
```
