"""Low-level implementation specification for work_scheduler_impl."""

from typing import Mapping, Optional, Sequence
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import work_scheduler
import subgraph
import agent_config
import node_config
import dag_storage


@singleton_type("agent_session")
class WorkScheduler(work_scheduler.WorkScheduler):
    """Implementation of work scheduler.

    GROUNDING:
    - Realizes task discovery and batch scheduling by querying dirty nodes and edge
      statuses in dag_storage.DagStorage, resolving role configurations from agent_config.RoleConfig
      and node configurations from node_config.NodeConfig, computing topological role
      precedence from role dependency declarations, and formatting prompt templates with historical feedback.
    """

    @operation
    @override
    def schedule_work(
        self,
        subgraph: Optional[subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> work_scheduler.WorkSchedule:
        """Discovers ready tasks and formats prompts into an execution schedule.

        GROUNDING:
        - Grounded via DagStorage to identify dirty nodes with clean upstream dependencies,
          DagSubgraph or directory filtering, and formatting task prompts with defect feedback.
        - Formats dependency paths on each scheduled task using user-facing file aliases rather
          than raw graph node addresses.
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

    @operation
    @override
    def format_task_prompt(self, nodes: Sequence[dag_storage.DagNode]) -> str:
        """Formats a synthesized task prompt for the supplied candidate nodes.

        GROUNDING:
        - Formats the aggregated prompt lines for the supplied dag_storage.DagNode sequence,
          composing each candidate node's prompt text into a single returned string.
        - For auditor sessions, lists configured blame targets against grounding files and
          includes read-only workspace directives, check_files, submit, and blame instructions.
        - For multi-node sessions, includes instructions directing target specification as file paths.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T04:05:49Z
# CHANGE: Align implementation with every interface operation: file target submission and resolution
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
