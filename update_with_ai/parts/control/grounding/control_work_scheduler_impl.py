"""Grounding specification for control_work_scheduler_impl."""

from __future__ import annotations
from typing import Mapping, Optional, Sequence
from support.lib.grounding_support import AgentSessionTier, InTier, only_elem, key, value
from parts.dag.grounding import dag_storage, dag_subgraph
from . import control_work_scheduler

__all__ = ["WorkScheduler"]


class WorkScheduler(
    control_work_scheduler.WorkScheduler,
    InTier[AgentSessionTier],
):
    """
    DISCHARGED:
    - WorkScheduler.schedule_work
    - WorkScheduler.compute_role_precedence
    """

    def schedule_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule:
        """
        COVERED:
        - When subgraph is provided, MUST query subgraph for ready candidates.
        - When dir_scope is provided, MUST scan directory for dirty nodes with clean deps.
        - MUST sort candidate tasks using dynamic role precedence from role dependency depth.
        - MUST limit returned tasks to max_batch_size when specified.
        """
        storage: dag_storage.DagStorage = self.get_singleton(dag_storage.DagStorage)
        sample_node = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("sample_unit"),
            role_address=dag_storage.RoleAddress("sample_role"),
        )
        task = control_work_scheduler.ScheduledTask(
            node=sample_node,
            task_prompt="Implement sample task",
            dependency_paths=["low/sample.pyi"],
            feedback_messages=[],
        )
        schedule = control_work_scheduler.WorkSchedule(tasks=[task])
        raise NotImplementedError

    def compute_role_precedence(
        self, role_dependencies: Mapping[str, Sequence[str]]
    ) -> Mapping[str, int]:
        """
        COVERED:
        - MUST assign integer rank matching longest path from root roles.
        """
        r_name = key(role_dependencies)
        deps = value(role_dependencies)
        depth_rank = len(deps)
        out = {r_name: depth_rank}
        raise NotImplementedError
