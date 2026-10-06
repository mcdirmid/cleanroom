"""Low-level interface specification for control_work_scheduler."""

from dataclasses import dataclass
from typing import Mapping, Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import dag_storage
import dag_subgraph


@data_type
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


@data_type
@dataclass(frozen=True)
class WorkSchedule:
    """Schedule containing ready tasks.

    Args:
        tasks: Ordered list of scheduled tasks.
    """

    tasks: Sequence[ScheduledTask]


@singleton_type("agent_session")
class WorkScheduler(InTier[AgentSessionTier], Protocol):
    """Scheduler that discovers ready dirty nodes and synthesizes prompts."""

    @operation
    def schedule_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> WorkSchedule:
        """Discovers ready tasks across subgraph or directory scope.

        POSTCONDITIONS:
        - When subgraph is provided, MUST query subgraph for ready candidates.
        - When dir_scope is provided, MUST scan directory for dirty nodes with clean deps.
        - MUST sort candidate tasks using dynamic role precedence from role dependency depth.
        - MUST limit returned tasks to max_batch_size when specified.
        """
        ...

    @operation
    def compute_role_precedence(
        self, role_dependencies: Mapping[str, Sequence[str]]
    ) -> Mapping[str, int]:
        """Computes topological depth for roles based on role dependencies.

        POSTCONDITIONS:
        - MUST assign integer rank matching longest path from root roles.
        """
        ...
