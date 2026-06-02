# MaxxAgentFramework Roadmap (Next Upgrades)

This file tracks **optional next incremental upgrades** beyond the current core + multi-agent implementation.

## Option A — Structured handoffs (deterministic multi-agent merging)
- **Goal**: Agents return structured JSON (instead of free-text), so orchestration can merge outputs reliably.
- **Work**:
  - Define a `HandoffPayload` schema (e.g. `summary`, `decisions`, `next_steps`, `artifacts`, `open_questions`).
  - Add a helper to validate/parse agent `[FINAL_ANSWER]` as JSON (fallback to wrapping plain text).
  - Update `Orchestrator` aggregators to merge by keys (with stable ordering).
  - Update `examples/multi_agent_example.py` to demonstrate JSON handoff between Researcher → Coder → Reviewer.

## Option B — Real delegation loop (manager spawns subtasks dynamically)
- **Goal**: A manager agent delegates work to sub-agents during a run and synthesizes results.
- **Work**:
  - Add a manager-oriented system prompt template emphasizing delegation.
  - Ensure `Crew.enable_delegation_tools()` is used in a hierarchical example.
  - Add a `run_manager_loop()` orchestration method that:
    - runs the manager
    - executes any delegate calls
    - feeds delegated results back
    - repeats until manager emits `[FINAL_ANSWER]` or max rounds.

## Option C — Persistence (audit/replay)
- **Goal**: Persist `ConversationMemory` + `TaskResult` to disk for replay, debugging, and audits.
- **Work**:
  - Add `ConversationMemory.to_json()` / `from_json()` methods.
  - Add an optional `RunLogger` that writes newline-delimited JSON events.
  - Add a replay script in `examples/` that loads a run and prints a timeline.

