# Security

**Related:** [Architecture](ARCHITECTURE.md) · [Advanced Topics](ADVANCED_TOPICS.md) · [Troubleshooting](TROUBLESHOOTING.md)

MaxxAgentFramework exposes powerful capabilities (file access, code execution, HTTP). This document describes the **safety model**, defaults, and deployment guidance for v0.1.

## Threat model

| Threat | Exposure | Mitigation in v0.1 |
|--------|----------|----------------------|
| Arbitrary code execution | `code_execution`, `execute_code` | Disabled by default; subprocess timeout; marked dangerous |
| Filesystem read/write outside workspace | File tools | Path canonicalization + `commonpath` check |
| Data exfiltration via HTTP tools | `read_url`, `web_search` | User-controlled endpoints; rate limit on advanced `web_search` |
| Prompt injection | LLM + tools | Application-level policy; not solved by framework alone |
| Resource exhaustion | Long outputs, tight loops | Output truncation, timeouts, max_steps |
| Untrusted model output | `[ACTION]` JSON | Schema validation before handler runs |

## Tool execution safety model

### Dangerous tools

Tools with `is_dangerous=True` do not run unless:

```python
ToolRunOptions(allow_dangerous_tools=True)
```

which is controlled by `AgentConfig.tools.allow_dangerous_tools` (default: `False`).

Dangerous tools include:

- Built-in: `file_ops`, `code_execution`
- Advanced: `read_file`, `write_file`, `list_files`, `execute_code`

### Tool result handling

Handlers should return `ToolResult` instead of raising. The agent loop continues on tool errors so the model can recover — ensure your prompts discourage infinite retry loops.

### JSON Schema validation

All tool arguments are validated with Draft 2020-12 JSON Schema before execution. Unknown properties are rejected when `additionalProperties: false`.

## Code execution sandboxing

`SandboxedPythonExecutor` uses:

- `subprocess.run([sys.executable, "-I", "-c", code], ...)`
- `timeout` enforced by subprocess
- `cwd` set to `workspace_root`
- stdout/stderr size limits

### Known limitations

- **Not a container** — no seccomp, no network isolation, no syscall filtering
- Malicious code may read environment variables, access network, or consume CPU until timeout
- `-I` isolates Python user site; it does not sandbox the OS

**Production recommendation:** run agents in containers or dedicated VMs; disable code execution unless required; use read-only filesystem mounts where possible.

**Planned:** Docker-backed executor — [Roadmap](ROADMAP.md).

## Path traversal prevention

File tools resolve paths with `_safe_join(workspace_root, relative_path)`:

1. Resolve `workspace_root` to an absolute path
2. Join with user-supplied relative path
3. Verify `commonpath([root, candidate]) == root`

Attempts to escape with `../` return validation or error results.

## Timeouts and resource limits

| Limit | Location | Default |
|-------|----------|---------|
| Tool cooperative timeout | `ToolConfig.timeout_s` | 20s |
| Code subprocess timeout | `SandboxedPythonExecutor.timeout_s` | 5s |
| Output truncation | `max_output_chars` | 50,000 |
| Agent steps | `AgentConfig.max_steps` | 10 |
| Document load size | `DocumentLoader.max_chars` | 2,000,000 |
| Web search rate | `TokenBucket` (advanced) | 30/min, burst 5 |

Registry-level timeouts cannot preempt a stuck in-process handler; use subprocess inside handlers for hard limits.

## Input validation

- Tool args: JSON Schema
- URLs: passed to httpx; ensure HTTPS and allowlists in production wrappers
- User queries: passed directly to LLM — sanitize or filter at application boundary if exposing to end users

## `web_search` considerations

Built-in and advanced `web_search` tools call **user-provided HTTP endpoints**. The framework does not ship a search provider.

- Only point endpoints you trust
- Use authentication on your search proxy
- Advanced variant applies token-bucket rate limiting

## Production deployment best practices

1. **Least privilege** — disable dangerous tools; narrow `workspace_root`
2. **Network policy** — egress allowlists for LLM and tool HTTP calls
3. **Secrets** — API keys via environment variables, not committed config
4. **Observability** — use `run_trace()` and external logging; audit tool calls
5. **Model trust** — treat model-produced `[ACTION]` as untrusted input (validated, but intent may be harmful)
6. **Multi-tenant** — one workspace root per tenant; never share `ToolRegistry` across tenants without isolation
7. **Updates** — pin dependencies (`httpx`, `jsonschema`); monitor CVEs

## Reporting issues

If you discover a security vulnerability, please report it responsibly to the project maintainers rather than opening a public issue with exploit details.

## Related configuration

```python
from maxx_agent.core.config import AgentConfig, ToolConfig

AgentConfig(
    tools=ToolConfig(
        allow_dangerous_tools=False,
        enable_code_execution=False,
        timeout_s=20.0,
        max_output_chars=50_000,
    ),
)
```
