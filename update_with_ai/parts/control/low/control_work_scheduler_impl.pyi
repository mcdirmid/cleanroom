# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T00:13:59Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: bdee55d316a1
# --- END CLEANROOM METADATA ---

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
    """Implementation of work scheduler.

    GROUNDING:
    - Realizes task discovery and batch scheduling by querying dirty nodes and edge
      statuses in DagStorage, computing topological role precedence from role dependency
      declarations, and formatting prompt templates with historical feedback.
    """

    @operation
    @override
    def schedule_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule:
        """Discovers ready tasks and formats prompts into an execution schedule.

        GROUNDING:
        - Grounded via DagStorage to identify dirty nodes with clean upstream dependencies,
          DagSubgraph or directory filtering, and formatting task prompts with defect feedback.
        """
        ...

    @operation
    @override
    def compute_role_precedence(
        self, role_dependencies: Mapping[str, Sequence[str]]
    ) -> Mapping[str, int]:
        """Calculates topological depth of roles based on declared dependencies.

        GROUNDING:
        - Grounded via DAG longest-path calculation over declared role dependencies
          to assign dynamic execution depths without hardcoded orderings.
        """
        ...
