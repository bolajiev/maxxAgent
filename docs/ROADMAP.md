# Roadmap

**Related:** [Quality Metrics](QUALITY_METRICS.md) · [Architecture](ARCHITECTURE.md) · [FAQ](FAQ.md)

This roadmap describes planned work for MaxxAgentFramework. **v0.1.0** is a framework scaffold: core loop, tools, memory, backends, multi-agent, RAG building blocks, and sandboxed execution.

For incremental upgrade ideas from early development, see also [../plan.md](../plan.md).

---

## Phase 1 — Stability (v0.1 release)

**Goal:** Trustworthy framework for integrators and demo-ready hero path.

| Item | Status | Notes |
|------|--------|-------|
| Core ReAct agent + tool registry | Done | `maxx_agent/core/` |
| LLM backends (HF, OpenAI, custom HTTP) | Done | `backends/llm_client.py` |
| Multi-agent Crew + Orchestrator | Done | `multi_agent/` |
| RAG loader + in-memory retriever | Done | `rag/` |
| Sandboxed Python executor | Done | `execution/sandbox.py` |
| Advanced tools pack | Done | `tools/advanced_tools.py` |
| `run_trace()` observability | Done | `Agent.run_trace` |
| MIT LICENSE | Done | `LICENSE` |
| Documentation suite | Done | `docs/` |
| Parser resilience (retry/repair) | Planned | Auto re-prompt on `AgentParseError` |
| Comprehensive error messages | Planned | Actionable hints in exceptions |
| Unit + integration tests | Planned | `tests/` with pytest |
| CI/CD (GitHub Actions) | Planned | lint + test on PR |
| Dependency pinning | Planned | Lock files or upper bounds |
| Type coverage 95%+ | Planned | mypy in CI |
| Hero E2E example | Planned | `examples/demo_full_agent.py` — RAG + tools + trace |

### From internal plan (merge into Phase 1–2)

**Structured handoffs (Option A)**

- Define `HandoffPayload` schema: `summary`, `decisions`, `next_steps`, `artifacts`, `open_questions`
- Parse `[FINAL_ANSWER]` as JSON with plain-text fallback
- Update `Orchestrator` aggregators for key-based merge

**Persistence (Option C — partial in Phase 1)**

- `ConversationMemory.to_json()` / `from_json()`
- Optional `RunLogger` (JSONL events)
- Replay script in `examples/`

---

## Phase 2 — Robustness (v0.2)

**Goal:** Production-adjacent behavior for real models and long-running workflows.

| Item | Description |
|------|-------------|
| Dynamic delegation loop | Manager agent spawns subtasks via `delegate`; `run_manager_loop()` on Orchestrator |
| RAG persistence | Save/load vector indices to disk |
| Production embedders | OpenAI, HF, local model adapters (replace `LocalHashEmbedder` default) |
| Database document loader | SQL/NoSQL sources in `DocumentLoader` |
| Docker sandbox | Container-isolated `execute_code` |
| Cost tracking | Token/cost metadata on `StepLog`; wrapper around `LLMClient` |
| Async support (optional) | `async def run` / async tool handlers |
| Pre-fetch RAG hook | Optional `Agent` config to inject retrieval before first LLM call |
| `MaxxClient` | First-class backend matching Maxx inference API |

---

## Phase 3 — Production (v1.0)

**Goal:** Operable product surface for teams.

| Item | Description |
|------|-------------|
| CLI | `maxx run "prompt"` |
| HTTP API server | FastAPI agent endpoint |
| Web UI | Optional chat/debug UI |
| Performance | Prompt caching, batch tool calls where safe |
| Structured logging | JSON logs, correlation IDs |
| Conversation replay | Full audit trail from persisted runs |
| Monitoring hooks | LangSmith, OpenTelemetry, or similar |
| Sphinx / MkDocs | Auto-generated API docs (optional) |

---

## Phase 4 — Ecosystem

**Goal:** Community and vertical integrations.

- Model fine-tuning guide for agent-specific behaviors
- Integration recipes: Slack, Discord, email, webhooks
- Community plugin registry for tools and backends
- Benchmarks and evaluations (tool-use accuracy, safety regressions)
- Template projects (research agent, coding agent, support bot)

---

## Versioning policy

- **0.x** — API may change; document breaking changes in release notes
- **1.0** — Stable public API for `core`, `backends`, and tool contracts

---

## How to contribute

Pick an item from Phase 1 or 2 and open a PR. See [Development](DEVELOPMENT.md).

When a roadmap item ships, move it to **Done** in this file and note the version in [Quality Metrics](QUALITY_METRICS.md).
