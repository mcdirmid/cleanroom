# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 0dd06aa23e9f
# LOW_QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for control_attribution_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
import control_attribution
import dag_storage
import src_metadata


@singleton_type("agent_session")
class AttributionCoordinator(
    control_attribution.AttributionCoordinator,
    InTier[AgentSessionTier],
):
    """Implementation of attribution coordinator.

    GROUNDING:
    - Coordinates upstream defect blame and failure reporting by validating that blame
      targets are declared upstream dependencies, enforcing feedback dependency permissions
      from NodeConfig, enforcing single-paragraph feedback rules, updating culprit cleanliness
      and feedback records in DagStorage, and transitioning affected session nodes to
      attributed or failed states.
    """

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
        """Attributes defect to an upstream dependency and requests reprocessing.

        GROUNDING:
        - Grounded via DagStorage to verify upstream dependency edges, verifies
          that the culprit node role is in the source role's feedback dependencies
          via NodeConfig, checks for single-paragraph compliance, appends feedback
          and marks dirty status on the culprit in DagStorage, and cascades failure
          to in-batch dependent nodes.
        """
        ...

    @operation
    @override
    def fail_target(
        self,
        target_node: dag_storage.DagNode,
        explanation: str,
        in_batch_dependents: Optional[Sequence[dag_storage.DagNode]] = None,
    ) -> control_attribution.AttributionOutcome:
        """Records a task failure and fails downstream in-batch dependent nodes.

        GROUNDING:
        - Grounded via DagStorage diagnostic logging and dirty status preservation
          on the failed target, alongside cascading failure marking across downstream
          in-batch dependent nodes.
        """
        ...
