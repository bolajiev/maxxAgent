"""
Coordination logic for multi-agent execution.

Patterns supported:
- Sequential: A -> B -> C (ordered tasks, optionally passing prior outputs)
- Parallel: run tasks concurrently, then aggregate outputs
- Hierarchical: manager task + delegated subtasks + manager synthesis
- Reactive: event-driven loop where results can spawn new tasks dynamically
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from enum import Enum

from maxxa_agent.multi_agent.crew import Crew
from maxxa_agent.multi_agent.task import Task, TaskResult


class CoordinationMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    REACTIVE = "reactive"


Aggregator = Callable[[Sequence[TaskResult]], str]
ReactivePolicy = Callable[[TaskResult], Sequence[Task]]


def default_aggregator(results: Sequence[TaskResult]) -> str:
    """Combine results into a readable merged report."""
    parts: list[str] = []
    for r in results:
        header = f"== {r.agent_name} ({'ok' if r.success else 'error'}) =="
        parts.append(header)
        if r.success:
            parts.append(r.output.strip())
        else:
            parts.append((r.error or "unknown error").strip())
    return "\n\n".join([p for p in parts if p.strip()]).strip()


@dataclass(slots=True)
class OrchestrationResult:
    """A structured output of an orchestration run."""

    results: list[TaskResult]
    aggregated_output: str
    mode: CoordinationMode


class Orchestrator:
    """Executes Tasks against a Crew using a chosen coordination pattern."""

    def __init__(self, *, crew: Crew, aggregator: Aggregator | None = None) -> None:
        self.crew = crew
        self.aggregator: Aggregator = aggregator or default_aggregator

    def run_sequential(
        self,
        tasks: Sequence[Task],
        *,
        pass_context: bool = True,
    ) -> OrchestrationResult:
        """
        Run tasks in order.

        If `pass_context` is True, each subsequent task receives a context dict
        containing prior results under `prior_results`.
        """
        results: list[TaskResult] = []
        for t in tasks:
            if pass_context and results:
                ctx = {"prior_results": [asdict(r) for r in results]}
                t = Task(
                    description=t.description,
                    assigned_agent=t.assigned_agent,
                    context=ctx,
                    metadata=t.metadata,
                )
            results.append(self.crew.run_task(t))
        return OrchestrationResult(
            results=results,
            aggregated_output=self.aggregator(results),
            mode=CoordinationMode.SEQUENTIAL,
        )

    def run_parallel(
        self,
        tasks: Sequence[Task],
        *,
        max_workers: int = 3,
    ) -> OrchestrationResult:
        """Run tasks concurrently and aggregate results."""
        results: list[TaskResult] = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(self.crew.run_task, t): t for t in tasks}
            for fut in as_completed(futs):
                results.append(fut.result())
        # preserve the original order for readability if possible
        results_by_id = {r.task_id: r for r in results}
        ordered = [results_by_id.get(t.task_id) for t in tasks]
        ordered_results = [r for r in ordered if r is not None]
        return OrchestrationResult(
            results=ordered_results,
            aggregated_output=self.aggregator(ordered_results),
            mode=CoordinationMode.PARALLEL,
        )

    def run_hierarchical(
        self,
        *,
        manager_task: Task,
        subtasks: Sequence[Task],
        synthesis_agent: str | None = None,
        max_workers: int = 3,
    ) -> OrchestrationResult:
        """
        Hierarchical pattern:
        - run `subtasks` (optionally in parallel)
        - run a manager/synthesis task that combines subtask outputs

        If `synthesis_agent` is provided, it overrides `manager_task.assigned_agent`.
        """
        if subtasks:
            sub_result = self.run_parallel(subtasks, max_workers=max_workers)
        else:
            sub_result = OrchestrationResult([], "", CoordinationMode.PARALLEL)

        synth_task = Task(
            description=manager_task.description,
            assigned_agent=synthesis_agent or manager_task.assigned_agent,
            context={"subtask_results": [asdict(r) for r in sub_result.results]},
            metadata=manager_task.metadata,
        )
        manager_result = self.crew.run_task(synth_task)

        results = list(sub_result.results) + [manager_result]
        return OrchestrationResult(
            results=results,
            aggregated_output=self.aggregator(results),
            mode=CoordinationMode.HIERARCHICAL,
        )

    def run_reactive(
        self,
        initial_tasks: Sequence[Task],
        *,
        policy: ReactivePolicy,
        max_rounds: int = 5,
        max_workers: int = 3,
    ) -> OrchestrationResult:
        """
        Reactive pattern: run tasks, then allow results to spawn new tasks.

        The `policy` callback is invoked for each TaskResult and may return new Tasks.
        The loop continues until no tasks remain or `max_rounds` is exceeded.
        """
        pending: list[Task] = list(initial_tasks)
        results: list[TaskResult] = []

        for _round in range(1, max_rounds + 1):
            if not pending:
                break

            batch = list(pending)
            pending.clear()
            batch_result = self.run_parallel(batch, max_workers=max_workers)
            results.extend(batch_result.results)

            for r in batch_result.results:
                for new_task in policy(r) or ():
                    pending.append(new_task)

        return OrchestrationResult(
            results=results,
            aggregated_output=self.aggregator(results),
            mode=CoordinationMode.REACTIVE,
        )

