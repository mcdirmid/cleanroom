"""Low-level implementation specification for control_work_scheduler_impl."""

from typing import Mapping, Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import control_work_scheduler
import dag_subgraph


@singleton_type("agent_session")
class WorkScheduler(
    control_work_scheduler.WorkScheduler,
    InTier[AgentSessionTier],
):
    """Implementation of work scheduler."""

    @operation
    @override
    def schedule_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule:
        ...

    @operation
    @override
    def compute_role_precedence(
        self, role_dependencies: Mapping[str, Sequence[str]]
    ) -> Mapping[str, int]:
        ...
