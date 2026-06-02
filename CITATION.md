# Citation

If you use **MaxxAgentFramework** in academic work, please cite the software package and (when applicable) the specific version you used.

## Recommended citation (software)

> MaxxAgentFramework contributors. (2026). *MaxxAgentFramework: An open-source agentic AI framework with ReAct reasoning, tools, and multi-agent orchestration* (Version 0.1.0) [Computer software]. https://github.com/bolajiev/maxxAgent

Update the version string if you cite a release other than 0.1.0.

## BibTeX

```bibtex
@software{maxxagentframework2026,
  author       = {{MaxxAgentFramework contributors}},
  title        = {MaxxAgentFramework: An Open-Source Agentic AI Framework},
  year         = {2026},
  version      = {0.1.0},
  url          = {https://github.com/bolajiev/maxxAgent},
  note         = {ReAct-style agents, tool registry, multi-agent crews, RAG, and sandboxed execution}
}
```

## APA (7th edition)

MaxxAgentFramework contributors. (2026). *MaxxAgentFramework* (Version 0.1.0) [Computer software]. https://github.com/bolajiev/maxxAgent

## Components to mention in methods (optional)

When describing your experimental setup, you may reference these architectural elements:

| Component | Description |
|-----------|-------------|
| Agent loop | Tag-based ReAct: THOUGHT, ACTION, OBSERVATION, FINAL_ANSWER |
| Tools | JSON Schema–validated tool calls via `ToolRegistry` |
| Memory | Sliding-window `ConversationMemory` with optional summarization |
| Multi-agent | `Crew` and `Orchestrator` coordination patterns |
| RAG | `DocumentLoader`, `TextSplitter`, `Retriever` (in-memory index in v0.1) |
| Execution | `SandboxedPythonExecutor` (subprocess isolation) |

## Reproducibility

Record for your paper or appendix:

- Python version (3.10+)
- Package version: `import maxxa_agent; print(maxxa_agent.__version__)`
- LLM backend and model identifier
- `AgentConfig` settings (`max_steps`, `temperature`, tool flags)
- Commit hash or release tag

## License

MaxxAgentFramework is released under the **MIT License**. See [LICENSE](LICENSE).

## Contact

For citation corrections or to register a DOI for a formal release, contact the maintainers via your project’s issue tracker.
