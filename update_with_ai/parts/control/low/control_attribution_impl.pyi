"""Low-level implementation specification for control_attribution_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import control_attribution
import dag_storage


@singleton_type("agent_session")
class AttributionCoordinator(
    control_attribution.AttributionCoordinator,
    InTier[AgentSessionTier],
):
    """Implementation of attribution coordinator."""

    @operation
    @override
    def blame_target(
        self,
        source_node: dag_storage.DagNode,
        blame_target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependencies: Optional[Sequence[dag_storage.DagNode]] = None,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        ...

    @operation
    @override
    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        ...
