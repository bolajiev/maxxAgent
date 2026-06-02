# Changelog

All notable changes to **MaxxAgentFramework** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Renamed Python package `maxxa_agent` → `maxx_agent` (cleaner import: `from maxx_agent import Agent`)
- PyPI/distribution name: `maxx-agent`
- Public API exports from `maxx_agent` root and `maxx_agent.backends`
- README: CI badge, tagline, top-of-page code sample

---

## [0.1.0] - 2026-06-02

### Added

- Core ReAct agent loop (`Agent.run`, `Agent.run_trace`)
- Tool registry with JSON Schema validation (`ToolSpec`, `ToolResult`, `ToolRegistry`)
- Built-in tools: `read_url`, `web_search`, `file_ops`, `code_execution`
- Conversation memory with sliding window and optional summarization hook
- LLM backends: `CustomEndpointClient`, `HFInferenceClient`, `OpenAIClient` (optional)
- Multi-agent: `Crew`, `Task`, `Orchestrator` (sequential, parallel, hierarchical, reactive)
- RAG: `DocumentLoader`, `TextSplitter`, `Retriever`, `LocalHashEmbedder`
- Sandboxed execution: `SandboxedPythonExecutor`
- Advanced tools: `read_file`, `write_file`, `list_files`, `execute_code`, `query_knowledge_base`
- Examples: multi-agent, RAG, code execution
- Documentation under `docs/`

[Unreleased]: https://github.com/bolajiev/maxxAgent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/bolajiev/maxxAgent/releases/tag/v0.1.0
