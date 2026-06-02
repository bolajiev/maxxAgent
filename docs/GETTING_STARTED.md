# Getting Started

**Related:** [Architecture](ARCHITECTURE.md) · [API Reference](API_REFERENCE.md) · [Examples](EXAMPLES.md)

This tutorial walks you through MaxxAgentFramework in five short sections (~15 minutes total).

## Prerequisites

- Python 3.10+
- Git (optional, for source install)

## Install

```bash
git clone https://github.com/bolajiev/maxxAgent.git
cd maxxAgent

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -e .
pip install python-dotenv   # optional, for load_env_file()
```

Optional OpenAI backend:

```bash
pip install -e ".[openai]"
```

Configure environment:

```bash
copy .env.example .env   # Windows
cp .env.example .env     # macOS/Linux
```

Edit `.env` and set `MAXX_LLM_ENDPOINT_URL` to your server.

---

## 1. Basic agent setup (~3 min)

Use environment variables (no hardcoded URLs in code):

```python
from maxx_agent.backends.llm_client import CustomEndpointClient
from maxx_agent.core.agent import Agent
from maxx_agent.core.config import AgentConfig
from maxx_agent.core.tools import ToolRegistry
from maxx_agent.settings import (
    load_env_file,
    llm_auth_headers,
    llm_endpoint_url,
    llm_request_timeout_s,
    workspace_root,
)

load_env_file()

llm = CustomEndpointClient(
    endpoint_url=llm_endpoint_url(),
    request_timeout_s=llm_request_timeout_s(),
    headers=llm_auth_headers(),
)

tools = ToolRegistry.with_builtins(
    workspace_root=workspace_root(),
    enable_code_execution=False,
)

agent = Agent(
    llm=llm,
    config=AgentConfig(max_steps=10, temperature=0.2),
    tools=tools,
)

answer = agent.run("What is MaxxAgentFramework?")
print(answer)
```

Your endpoint must return generated text in one of the supported JSON shapes (see [API Reference — CustomEndpointClient](API_REFERENCE.md#customendpointclient)).

**Offline demo (no LLM server):**

```bash
python examples/multi_agent_example.py
```

---

## 2. Adding custom tools (~5 min)

Tools are functions that return `ToolResult` and declare a JSON Schema for arguments.

```python
from maxx_agent.core.tools import ToolRegistry, ToolSpec, ToolResult

def greet(args: dict) -> ToolResult:
    name = args["name"]
    return ToolResult(result={"message": f"Hello, {name}!"})

registry = ToolRegistry()
registry.register(
    ToolSpec(
        name="greet",
        description="Greet a person by name.",
        args_schema={
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 1}},
            "required": ["name"],
            "additionalProperties": False,
        },
        handler=greet,
    )
)
```

The model must emit:

```text
[ACTION] {"tool": "greet", "args": {"name": "Maxx"}}
```

Update `AgentConfig.system_prompt` if your model needs stronger format instructions.

---

## 3. Using different LLM backends (~5 min)

### Custom HTTP (Maxx or any server)

```python
from maxx_agent.backends.llm_client import CustomEndpointClient

llm = CustomEndpointClient(
    endpoint_url="https://your-server/v1/generate",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
)
```

### Hugging Face Inference

```python
from maxx_agent.backends.llm_client import HFInferenceClient

llm = HFInferenceClient(
    model_id="meta-llama/Llama-3.2-3B-Instruct",
    api_token="hf_...",
)
```

### OpenAI

```bash
pip install -e ".[openai]"
```

```python
from maxx_agent.backends.llm_client import OpenAIClient

llm = OpenAIClient(model="gpt-4o-mini", api_key="sk-...")
```

Pass the client to `Agent(llm=llm, ...)`. `BackendConfig` is optional metadata only.

---

## 4. Memory and conversation management (~5 min)

Each `Agent` has its own `ConversationMemory`. Messages accumulate across `run()` calls on the same instance.

```python
from maxx_agent.core.config import AgentConfig, MemoryConfig
from maxx_agent.core.memory import ConversationMemory

memory = ConversationMemory(window_size=10)

agent = Agent(
    llm=llm,
    config=AgentConfig(memory=MemoryConfig(window_size=10)),
    memory=memory,
)

agent.run("My name is Alex.")
agent.run("What is my name?")  # Uses recent context from memory
```

### Optional summarization

```python
def simple_summarizer(messages):
    lines = [f"{m.role}: {m.content[:200]}" for m in messages]
    return "Earlier conversation:\n" + "\n".join(lines)

memory = ConversationMemory(
    window_size=5,
    summarizer=simple_summarizer,
    summary_trigger_count=20,
)
```

When the conversation grows, older messages (outside the window) are compressed into a `[SUMMARY]` block in prompts.

---

## 5. Debugging with `run_trace()` (~5 min)

**Implemented:** inspect every step of the ReAct loop.

```python
trace = agent.run_trace("List files in the workspace and summarize README.")

print("Final:", trace.final_answer)
for step in trace.steps:
    print(f"\n--- Step {step.step} ---")
    if step.thought:
        print("Thought:", step.thought[:200])
    if step.action:
        print("Action:", step.action)
    if step.observation:
        print("Observation:", step.observation)
    if step.final_answer:
        print("Final:", step.final_answer)
```

Use this when you see `AgentParseError` or unexpected tool calls. See [Troubleshooting](TROUBLESHOOTING.md).

---

## Next steps

- [Advanced Topics](ADVANCED_TOPICS.md) — multi-agent, RAG, sandboxing
- [Examples](EXAMPLES.md) — runnable scripts
- [Security](SECURITY.md) — before enabling dangerous tools
