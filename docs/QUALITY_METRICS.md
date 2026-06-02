# Quality Metrics

**Related:** [Roadmap](ROADMAP.md) · [Security](SECURITY.md) · [Development](DEVELOPMENT.md)

This document defines what **quality** means for MaxxAgentFramework and how we measure progress toward release readiness.

**Current baseline (v0.1.0):** functional core with examples; **no automated test suite yet**.

---

## Dimensions of quality

| Dimension | Definition |
|-----------|------------|
| **Reliability** | Agent completes tasks without crashes; predictable errors |
| **Safety** | Tools cannot escape workspace or run dangerous ops by default |
| **Performance** | Low framework overhead; bounded latency and output size |
| **Usability** | Clear docs, runnable examples, actionable error messages |
| **Maintainability** | Typed code, tests, CI, documented APIs |

---

## Reliability targets

| Metric | Target (v1.0) | v0.1 baseline |
|--------|---------------|---------------|
| Parse success rate (compliant model) | > 95% on golden prompts | Depends on model; strict tags |
| Tool error recovery | Loop continues; model can retry | Implemented |
| Unhandled exceptions in `Agent.run` | < 1% on golden set | No golden set yet |
| Example scripts pass CI | 100% | Manual only |

**Planned measurements:**

- Golden-file tests for tag parsing (`_extract_blocks`, `_parse_action`)
- Integration tests with `ScriptedLLM` backend

---

## Test coverage targets

| Scope | Target | v0.1 |
|-------|--------|------|
| `core.agent` | 85%+ | 0% |
| `core.tools` | 90%+ | 0% |
| `core.memory` | 80%+ | 0% |
| `rag.retriever` | 80%+ | 0% |
| `execution.sandbox` | 85%+ | 0% |
| **Overall** | **80%+** | **0%** |

When tests land, run:

```bash
pytest --cov=maxx_agent --cov-report=term-missing
```

---

## Performance targets (guidance)

Framework overhead (excluding LLM latency) should stay small:

| Operation | Guideline |
|-----------|-----------|
| `build_prompt` | < 10 ms for 5 memory messages |
| `ToolRegistry.run` (no I/O) | < 5 ms |
| `Retriever.query` (in-memory, <10k chunks) | < 100 ms |

Token efficiency is primarily the integrator's responsibility (prompt design, memory window). Recommend:

- `MemoryConfig.window_size` tuned to task
- Summarization for long sessions
- RAG `top_k` limited to what fits context

---

## Safety checklist

Use before enabling dangerous tools in any environment:

- [ ] `allow_dangerous_tools=False` unless required
- [ ] `enable_code_execution=False` unless required
- [ ] `workspace_root` points to an isolated directory
- [ ] File tools use path join guards (built-in)
- [ ] Subprocess timeouts configured
- [ ] `max_output_chars` set appropriately
- [ ] `max_steps` capped (default 10)
- [ ] `web_search` endpoint is trusted
- [ ] Secrets not in source control
- [ ] Production runs in container/VM if code execution enabled

Full detail: [Security](SECURITY.md).

---

## Documentation completeness checklist

Release gate for minor versions:

- [ ] [README.md](../README.md) quickstart runs
- [ ] [API_REFERENCE.md](API_REFERENCE.md) lists all public classes
- [ ] New tools documented in tool matrix
- [ ] [EXAMPLES.md](EXAMPLES.md) lists every script in `examples/`
- [ ] Breaking changes noted in README or CHANGELOG
- [ ] Planned features marked **Planned** not **Implemented**

---

## Type coverage

| Target | Tool | v0.1 |
|--------|------|------|
| 95%+ typed public API | mypy | Not enforced in CI |

---

## User feedback incorporation

1. **Issues** — tag as `bug`, `docs`, `enhancement`
2. **Triage** — Phase 1 for regressions and demo blockers
3. **Release notes** — summarize user-facing fixes per version
4. **Roadmap updates** — promoted items when repeated requests align with vision

---

## Release readiness (v0.1 → v0.2)

**v0.1 (current)** — framework preview:

- Documentation complete
- Examples runnable
- LICENSE present
- Honest "not production-ready" positioning

**v0.2 gate** — add:

- pytest suite + CI green
- Parser retry helper
- At least one real-LLM integration test (optional, skipped in CI without secrets)

**v1.0 gate** — add:

- CLI or HTTP server
- Persistence/replay
- Security review for sandbox path
