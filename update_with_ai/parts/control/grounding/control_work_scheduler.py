"""Grounding specification for control_work_scheduler."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Optional, Protocol, Sequence
from support.lib.grounding_support import AgentSessionTier, InTier
from parts.dag.grounding import dag_storage, dag_subgraph

__all__ = ["ScheduledTask", "WorkSchedule", "WorkScheduler"]


@dataclass(frozen=True)
class ScheduledTask:
    node: dag_storage.DagNode
    task_prompt: str
    dependency_paths: Sequence[str]
    feedback_messages: Sequence[dag_storage.FeedbackMessage]


@dataclass(frozen=True)
class WorkSchedule:
    tasks: Sequence[ScheduledTask]


class WorkScheduler(InTier[AgentSessionTier], Protocol):
    def schedule_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> WorkSchedule:
        """
        DEFERRED:
        - When subgraph is provided, MUST query subgraph for ready candidates.
        - When dir_scope is provided, MUST scan directory for dirty nodes with clean deps.
        - MUST sort candidate tasks using dynamic role precedence from role dependency depth.
        - MUST limit returned tasks to max_batch_size when specified.
        """
        raise NotImplementedError

    def compute_role_precedence(
        self, role_dependencies: Mapping[str, Sequence[str]]
    ) -> Mapping[str, int]:
        """
        DEFERRED:
        - MUST assign integer rank matching longest path from root roles.
        """
        raise NotImplementedError
