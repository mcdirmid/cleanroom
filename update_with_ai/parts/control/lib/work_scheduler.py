# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-06T10:45:00Z
# CHANGE: new file
# CODE_HASH: 7bdde095c67d
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Optional, Protocol, Sequence
from update_with_ai.parts.dag.lib import dag_storage, subgraph


@dataclass(frozen=True)
class ScheduledTask:
    """A scheduled task ready for processing.

    Args:
        node: Target DAG node.
        task_prompt: Synthesized prompt string.
        dependency_paths: Declared upstream dependency file paths.
        feedback_messages: Sequence of unaddressed feedback messages.
    """

    node: dag_storage.DagNode
    task_prompt: str
    dependency_paths: Sequence[str]
    feedback_messages: Sequence[dag_storage.FeedbackMessage]


@dataclass(frozen=True)
class WorkSchedule:
    """Schedule containing ready tasks."""

    tasks: Sequence[ScheduledTask]


class WorkScheduler(Protocol):
    """Schedules ready dirty nodes across subgraph or directory scope."""

    # Contract: Discovers ready dirty tasks across subgraph or directory scope, sorts by dynamic role precedence, and limits to max_batch_size.
    def schedule_work(
        self,
        subgraph: Optional[subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> WorkSchedule: ...

    # Contract: Computes topological depth for roles based on role dependencies matching longest path from root roles.
    def compute_role_precedence(
        self, role_dependencies: Mapping[str, Sequence[str]]
    ) -> Mapping[str, int]: ...

    # Contract: Formats aggregated synthesized task prompt for candidate nodes with defect feedback and role directives.
    def format_task_prompt(
        self, nodes: Sequence[dag_storage.DagNode]
    ) -> str: ...
