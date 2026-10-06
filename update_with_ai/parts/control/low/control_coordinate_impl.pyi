"""Low-level implementation specification for control_coordinate_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import control_attribution
import control_coordinate
import control_submit
import control_verification
import control_work_scheduler
import dag_storage
import dag_subgraph


@singleton_type("agent_session")
class SessionCoordinator(
    control_coordinate.SessionCoordinator,
    InTier[AgentSessionTier],
):
    """Implementation of session coordinator facade.

    GROUNDING:
    - Central session coordination facade managing session node states and dispatching
      to WorkScheduler, VerificationEvaluator, SubmissionCoordinator, and AttributionCoordinator
      within the agent session tier.
    """

    @property
    @override
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        """Retrieves nodes currently in OPEN state.

        GROUNDING:
        - Grounded via in-memory dictionary filtering nodes whose tracked state is OPEN.
        """
        ...

    @operation
    @override
    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: control_coordinate.TargetState = control_coordinate.TargetState.OPEN,
    ) -> None:
        """Registers a target node with an alias and initial state.

        GROUNDING:
        - Grounded via internal session dictionaries recording DagNode references,
          alias strings, and target states.
        """
        ...

    @operation
    @override
    def resolve_default_target(self) -> Optional[dag_storage.DagNode]:
        """Resolves the default target node when omitted from command invocation.

        GROUNDING:
        - Grounded via single open target check or inspecting file modification
          timestamps from the filesystem for registered target files.
        """
        ...

    @operation
    @override
    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]:
        """Resolves a DagNode instance from a string alias.

        GROUNDING:
        - Grounded via alias lookup dictionary mapping string names to registered DagNode instances.
        """
        ...

    @operation
    @override
    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        """Resolves the alias string corresponding to a DagNode.

        GROUNDING:
        - Grounded via reverse alias dictionary mapping DagNode instances to canonical alias strings.
        """
        ...

    @operation
    @override
    def dispatch_get_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule:
        """Dispatches work discovery to the work scheduler.

        GROUNDING:
        - Grounded via WorkScheduler.schedule_work from control_work_scheduler,
          populating newly discovered tasks as OPEN nodes in the session registry.
        """
        ...

    @operation
    @override
    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> control_verification.VerificationResult:
        """Dispatches verification evaluation for a target or all open targets.

        GROUNDING:
        - Grounded via default target resolution and VerificationEvaluator.evaluate_verification
          from control_verification across the specified target or all open targets.
        """
        ...

    @operation
    @override
    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> control_coordinate.ControlDispatchOutcome:
        """Dispatches submission gating for a target.

        GROUNDING:
        - Grounded via default target resolution, SubmissionCoordinator.submit_target
          from control_submit, and updating node state to CLEAN upon successful submission.
        """
        ...

    @operation
    @override
    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        """Dispatches upstream defect attribution.

        GROUNDING:
        - Grounded via default target resolution, AttributionCoordinator.blame_target
          from control_attribution, updating source node to ATTRIBUTED, and marking
          dependent nodes FAILED.
        """
        ...

    @operation
    @override
    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        """Dispatches failure recording for a target.

        GROUNDING:
        - Grounded via default target resolution, AttributionCoordinator.fail_target
          from control_attribution, and marking dependent nodes FAILED.
        """
        ...
