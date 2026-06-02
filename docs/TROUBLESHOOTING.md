# Troubleshooting

**Related:** [Getting Started](GETTING_STARTED.md) · [API Reference](API_REFERENCE.md) · [Security](SECURITY.md)

## `ModuleNotFoundError: No module named 'maxx_agent'`

**Cause:** Package not installed and example run from wrong directory.

**Fix:**

```bash
cd /path/to/maxxAgent
pip install -e .
```

Or run examples from repo root (they add the parent path to `sys.path`).

---

## `AgentParseError`: Model output missing [ACTION] and [FINAL_ANSWER]

**Cause:** The LLM did not follow the ReAct tag format.

**Fix:**

1. Strengthen `AgentConfig.system_prompt` with explicit tag examples.
2. Use `run_trace()` to inspect `raw_model_output`:

```python
trace = agent.run_trace("your question")
print(trace.steps[-1].raw_model_output)
```

3. Fine-tune or choose a model that follows instructions.
4. **Planned:** built-in parser retry — see [Roadmap](ROADMAP.md).

**Valid action format:**

```text
[ACTION] {"tool": "read_url", "args": {"url": "https://example.com"}}
```

---

## `AgentParseError`: [ACTION] must be JSON

**Cause:** Malformed JSON in the `[ACTION]` block.

**Fix:** Ensure the model emits a single JSON object with `tool` and `args` keys. No trailing commas, no markdown fences inside the tag.

---

## Tool not found

**Symptom:** `ToolResult` with status `NOT_FOUND` or error mentions unknown tool.

**Fix:**

- List registered tools: `registry.list_specs()`
- Match tool name exactly (case-sensitive)
- Register advanced tools: `register_advanced_tools(registry, ...)`
- Do not assume builtins and advanced tools coexist unless you registered both

---

## Tool validation / `INVALID_ARGS`

**Symptom:** `ToolResult.status == "invalid_args"`.

**Fix:**

- Compare args to the tool's JSON Schema in [API Reference](API_REFERENCE.md)
- Ensure required fields are present
- Do not send extra keys if `additionalProperties: false`

---

## Dangerous tool disabled

**Symptom:** `Tool 'file_ops' is marked dangerous and is disabled.`

**Fix:**

```python
from maxx_agent.core.config import AgentConfig, ToolConfig

AgentConfig(tools=ToolConfig(allow_dangerous_tools=True))
```

Only enable in trusted environments. See [Security](SECURITY.md).

---

## `code_execution` / `execute_code` disabled

**Symptom:** Error mentions disabled by default.

**Fix:**

```python
ToolConfig(
    allow_dangerous_tools=True,
    enable_code_execution=True,  # for builtin code_execution
)
```

For advanced `execute_code`, set `enable_execution=True` in `register_advanced_tools`.

---

## Tool timeout

**Symptom:** `TIMEOUT` status or timeout error message.

**Notes:**

- `ToolConfig.timeout_s` is cooperative (measures elapsed time after handler returns)
- `SandboxedPythonExecutor` uses hard subprocess timeout
- Long-running handlers should use subprocess internally

**Fix:** Increase `timeout_s` or optimize the tool handler.

---

## `LLMBackendError`

**Cause:** HTTP failure or unexpected response from HF, OpenAI, or custom endpoint.

**Fix:**

- Verify URL, API keys, and network
- For `CustomEndpointClient`, ensure response includes `text`, `output`, or `choices[0].text`
- Check server logs
- Increase `request_timeout_s`

**Custom endpoint example response:**

```json
{"text": "model output here"}
```

---

## `RuntimeError`: Max steps exceeded

**Cause:** Agent did not produce `[FINAL_ANSWER]` within `max_steps`.

**Fix:**

- Increase `AgentConfig.max_steps`
- Check if tools keep failing (model stuck in retry loop)
- Use `run_trace()` to see repeated actions

---

## `web_search` requires endpoint_url

**Cause:** Built-in `web_search` has no default search provider.

**Fix:** Pass `endpoint_url` in tool args or use `register_advanced_tools(..., web_search_endpoint_url="https://...")`.

---

## RAG returns irrelevant results

**Cause:** `LocalHashEmbedder` is a demo embedder, not semantic-quality.

**Fix:**

- Implement a real `Embedder` (API or local model)
- Tune `chunk_size` / `chunk_overlap`
- Increase `top_k` or improve source documents

---

## Memory seems to "forget" earlier messages

**Cause:** `ConversationMemory` only includes the last `window_size` messages in prompts (default 5).

**Fix:**

- Increase `MemoryConfig.window_size`
- Add a `summarizer` for long conversations

---

## Debug mode

**Implemented today:**

```python
trace = agent.run_trace(query)
for s in trace.steps:
    print(s.step, s.action, s.observation)
```

**Planned:** verbose logging flag and JSONL export — [Roadmap](ROADMAP.md).

---

## Still stuck?

1. Read [Architecture](ARCHITECTURE.md) for expected flow
2. Run the closest [example](EXAMPLES.md)
3. Open an issue with `run_trace()` output (redact secrets)
