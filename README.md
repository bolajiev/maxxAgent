# Maxx Agent Framework

[![Tests](https://github.com/bolajiev/maxxAgent/actions/workflows/tests.yml/badge.svg)](https://github.com/bolajiev/maxxAgent/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)

**Repository:** [github.com/bolajiev/maxxAgent](https://github.com/bolajiev/maxxAgent)

> **Build agents that think, act, and remember.**  
> ReAct loop · JSON-schema tools · multi-agent crews · RAG · plug in your **Maxx** model via HTTP.

**Maxx Agent Framework** is an open-source Python library for **stateful, tool-using AI agents**. It provides a transparent ReAct-style loop (`Thought → Action → Observation → Final Answer`), a safe tool registry with JSON Schema validation, pluggable LLM backends (Hugging Face, OpenAI, or any custom HTTP endpoint), multi-agent crews, retrieval-augmented generation (RAG), and sandboxed code execution. Version **0.1** is a framework preview for integrators — not a hosted product.

```python
from maxx_agent import Agent, AgentConfig, ToolRegistry
from maxx_agent.backends import CustomEndpointClient
from maxx_agent.settings import load_env_file, llm_endpoint_url

load_env_file()
agent = Agent(
    llm=CustomEndpointClient(endpoint_url=llm_endpoint_url()),
    config=AgentConfig(max_steps=10),
    tools=ToolRegistry.with_builtins(workspace_root="."),
)
print(agent.run("What can you do?"))
```

## Key features

- **ReAct agent loop** — explicit tagged control flow with `Agent.run()` and `Agent.run_trace()`
- **Tool registry** — validate, execute, and capture tool results with safety gates
- **Memory** — conversation history with sliding context window and optional summarization
- **LLM backends** — `HFInferenceClient`, `OpenAIClient`, `CustomEndpointClient` (ideal for your own Maxx model server)
- **Multi-agent** — `Crew`, `Task`, and `Orchestrator` (sequential, parallel, hierarchical, reactive)
- **RAG** — document loading, chunking, embedding, and semantic retrieval
- **Sandboxed execution** — subprocess-based Python runner with timeouts and output limits
- **Advanced tools** — bounded file I/O, rate-limited search, knowledge-base queries

## Quick start

### 1. Clone and install

Requires **Python 3.10+**.

```bash
git clone https://github.com/bolajiev/maxxAgent.git
cd maxxAgent

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e .
# Optional OpenAI backend:
pip install -e ".[openai]"
# Optional: auto-load .env files in your scripts
pip install python-dotenv
```

> **Using a fork?** Replace the `git clone` URL with your fork. All runtime URLs and keys go in `.env`, not in source code.

### 2. Configure environment

```bash
# Windows
copy .env.example .env
# macOS/Linux
cp .env.example .env
```

Edit `.env` — set at least `MAXX_LLM_ENDPOINT_URL` to your inference server (see [.env.example](.env.example)).

| Variable | Purpose |
|----------|---------|
| `MAXX_LLM_ENDPOINT_URL` | Your Maxx / custom HTTP generate endpoint |
| `MAXX_LLM_API_KEY` | Optional bearer token |
| `MAXX_WORKSPACE_ROOT` | Root for file tools and sandbox |
| `MAXX_ALLOW_DANGEROUS_TOOLS` | `true` only in trusted setups |

Full list: [.env.example](.env.example) · [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#environment-variables)

### 3. Run an agent

```python
from maxx_agent import Agent, AgentConfig, ToolRegistry
from maxx_agent.backends import CustomEndpointClient
from maxx_agent.settings import load_env_file, llm_auth_headers, llm_endpoint_url, llm_request_timeout_s, workspace_root

load_env_file()  # no-op if python-dotenv not installed

agent = Agent(
    llm=CustomEndpointClient(
        endpoint_url=llm_endpoint_url(),
        request_timeout_s=llm_request_timeout_s(),
        headers=llm_auth_headers(),
    ),
    config=AgentConfig(max_steps=10),
    tools=ToolRegistry.with_builtins(
        workspace_root=workspace_root(),
        enable_code_execution=False,
    ),
)

print(agent.run("Explain what this framework does in one paragraph."))
```

### 4. Offline demo (no API keys)

```bash
python examples/multi_agent_example.py
python examples/rag_example.py
python examples/code_execution_example.py
```

## Architecture (overview)

```text
User → Agent → LLM (generate)
         ↑         ↓
      Memory ← parse [ACTION] / [FINAL_ANSWER]
         ↑         ↓
         └── ToolRegistry → Tools (HTTP, files, RAG, code, …)
```

Multi-agent workflows add `Crew` + `Orchestrator` on top of the same core `Agent`.

Deep dive: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Supported backends

| Backend | Class | Install |
|---------|-------|---------|
| Custom HTTP | `CustomEndpointClient` | core |
| Hugging Face Inference | `HFInferenceClient` | core |
| OpenAI | `OpenAIClient` | `pip install -e ".[openai]"` |

See [docs/API_REFERENCE.md](docs/API_REFERENCE.md#maxx_agentbackendsllm_client).

## Safety and security

- Dangerous tools (`file_ops`, `code_execution`, advanced file/code tools) are **disabled by default**
- Workspace-scoped file paths with traversal checks
- Tool argument validation via JSON Schema
- Subprocess timeouts and output truncation for code execution

**Not a container sandbox.** Review [docs/SECURITY.md](docs/SECURITY.md) before production use.

## Documentation

| Guide | Description |
|-------|-------------|
| [docs/README.md](docs/README.md) | Documentation hub |
| [Getting Started](docs/GETTING_STARTED.md) | Tutorials (~15 min) |
| [Architecture](docs/ARCHITECTURE.md) | Design and data flow |
| [API Reference](docs/API_REFERENCE.md) | Classes and methods |
| [Advanced Topics](docs/ADVANCED_TOPICS.md) | Multi-agent, RAG, sandboxing |
| [Examples](docs/EXAMPLES.md) | Example scripts |
| [Roadmap](docs/ROADMAP.md) | Planned releases |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues |
| [FAQ](docs/FAQ.md) | Frequently asked questions |

Internal upgrade notes: [plan.md](plan.md) (see [Roadmap](docs/ROADMAP.md) for the canonical plan).

## Contributing

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for setup, adding tools/backends, and the documentation policy.

## License

MIT — see [LICENSE](LICENSE).
