"""Low-level implementation specification for control_submit_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import control_submit
import dag_storage


@singleton_type("agent_session")
class SubmissionCoordinator(
    control_submit.SubmissionCoordinator,
    InTier[AgentSessionTier],
):
    """Implementation of submission coordinator."""

    @operation
    @override
    def submit_target(
        self,
        target_node: dag_storage.DagNode,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_submit.SubmissionOutcome:
        ...
