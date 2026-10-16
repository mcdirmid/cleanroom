# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T04:40:32Z
# CHANGE: Record the failing target's own FAILED state when dispatching fail
# CODE_HASH: 177e94e8c651
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---

"""Low-level implementation specification for control_coordinate_impl."""

from typing import Any, Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import agent_file_alias
import agent_node_config
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
    - Realizes control_coordinate.SessionCoordinator within the agent session tier by holding the
      mutable internal session dictionaries that map dag_storage.DagNode values to
      control_coordinate.TargetState values and alias strings to registered dag_storage.DagNode
      values, normalizing alias strings through agent_file_alias.AliasManager.to_alias, and
      synchronizing the active session nodes through agent_node_config.RoleConfig.set_nodes.
    - Dispatches work discovery to control_work_scheduler.WorkScheduler, verification evaluation
      to control_verification.VerificationEvaluator, submission gating to
      control_submit.SubmissionCoordinator, and blame or failure recording to
      control_attribution.AttributionCoordinator.
    - Aggregates each dispatched control action into a
      control_coordinate.ControlDispatchOutcome whose remaining open targets are read back from
      the internal session node state dictionary.
    """

    @property
    @override
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        """Retrieves nodes currently in OPEN state.

        GROUNDING:
        - Grounded via the internal session node state dictionary, filtering for the
          dag_storage.DagNode entries whose tracked control_coordinate.TargetState is OPEN.
        """
        ...

    @operation
    @override
    def reset_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Resets session node tracking to the specified nodes.

        GROUNDING:
        - Replaces the internal session node state dictionary entries with the supplied
          dag_storage.DagNode sequence, tracking each supplied node as a new open target so that
          open_targets reports exactly the reset nodes.
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
        - Mutates the internal session node state dictionary by inserting the supplied
          dag_storage.DagNode against the supplied control_coordinate.TargetState.
        - Normalizes the supplied alias string through agent_file_alias.AliasManager.to_alias,
          indexing the resulting agent_file_alias.FileAlias.relative_path text against the
          registered dag_storage.DagNode in the internal alias lookup and reverse alias lookup
          indices.
        """
        ...

    @operation
    @override
    def resolve_default_target(
        self, last_accessed_file: Optional[Any] = None
    ) -> Optional[dag_storage.DagNode]:
        """Resolves the default target node when omitted from command invocation.

        GROUNDING:
        - Grounded via the internal session node state dictionary to select the sole
          dag_storage.DagNode tracked as control_coordinate.TargetState.OPEN when a single open
          target remains, and via filesystem modification timestamps of the registered
          agent_file_alias.BoundFile.workspace_path files when multiple open targets remain,
          honoring the caller-supplied last accessed file when provided.
        """
        ...

    @operation
    @override
    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]:
        """Resolves a DagNode instance from a string alias.

        GROUNDING:
        - Resolves the alias string through agent_file_alias.AliasManager.to_alias and looks the
          resulting agent_file_alias.FileAlias.relative_path text up in the internal alias lookup
          index, falling back to normalized path suffix matching and role-compatible file proxy
          matching that checks role consistency against candidate dag_storage.DagNode values.
        """
        ...

    @operation
    @override
    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        """Resolves the alias string corresponding to a DagNode.

        GROUNDING:
        - Grounded via the internal reverse alias index, falling back to resolving user-facing
          file aliases via agent_node_config.NodeConfig source file aliases, configured blame
          targets, read-only/read-write paths, or configured role source patterns.
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
        - Grounded via control_work_scheduler.WorkScheduler.schedule_work with the supplied
          dag_subgraph.DagSubgraph, directory scope, and maximum batch size, returning the
          discovered control_work_scheduler.WorkSchedule.
        - Populates the internal session node state dictionary by registering each scheduled
          control_work_scheduler.ScheduledTask.node as control_coordinate.TargetState.OPEN.
        - Synchronizes the active session nodes by passing the resulting open target sequence to
          agent_node_config.RoleConfig.set_nodes.
        """
        ...

    @operation
    @override
    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> control_verification.VerificationResult:
        """Dispatches verification evaluation for a target or all open targets.

        GROUNDING:
        - Grounded via default target resolution to obtain the target dag_storage.DagNode, falling
          back to the sole open node when a supplied alias does not resolve directly in a
          single-open session, then evaluating each requested target through
          control_verification.VerificationEvaluator.evaluate_verification and combining the
          per-target control_verification.VerificationResult values into the returned result.
        - Grounded via the internal session node state dictionary to evaluate every
          control_coordinate.TargetState.OPEN target when the target alias is omitted.
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
        - Grounded via default target resolution and
          control_submit.SubmissionCoordinator.submit_target for the resolved
          dag_storage.DagNode with the supplied change summary and modification flag, falling
          back to the sole open node when a supplied alias does not resolve directly in a
          single-open session, and updating the internal session node state entry to
          control_coordinate.TargetState.CLEAN when the submission is accepted.
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
        - Grounded via default target resolution and matching the blame target alias against
          configured upstream blame targets via control_attribution.AttributionCoordinator.match_blame_target,
          registering the attributed upstream node in the session coordinator, guarding against
          self-blame, and invoking control_attribution.AttributionCoordinator.blame_target with the
          supplied explanation, updating the internal session node state entries to record the
          source node as control_coordinate.TargetState.ATTRIBUTED and the affected dependent nodes
          as control_coordinate.TargetState.FAILED.
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
        - Grounded via default target resolution and
          control_attribution.AttributionCoordinator.fail_target for the resolved
          dag_storage.DagNode with the supplied explanation, falling back to the sole open node
          when a supplied alias does not resolve directly in a single-open session, updating the
          internal session node state entries to record the failing target node itself as
          control_coordinate.TargetState.FAILED and the affected dependent nodes as
          control_coordinate.TargetState.FAILED.
        """
        ...
