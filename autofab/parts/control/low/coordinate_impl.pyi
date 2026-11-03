"""Low-level implementation specification for coordinate_impl."""

from typing import Any, Optional, Sequence
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton
from session import AgentSessionTier
import file_alias
import node_config
import attribution
import coordinate
import submit
import verification
import work_scheduler
import dag_storage
import subgraph


@singleton_type("agent_session")
class SessionCoordinator(coordinate.SessionCoordinator):
    """Implementation of session coordinator facade.

    GROUNDING:
    - Realizes coordinate.SessionCoordinator within the agent session tier by holding the
      mutable internal session dictionaries that map dag_storage.DagNode values to
      coordinate.TargetState values and alias strings to registered dag_storage.DagNode
      values, normalizing alias strings through file_alias.AliasManager.to_alias, and
      synchronizing the active session nodes through node_config.RoleConfig.set_nodes.
    - Dispatches work discovery to work_scheduler.WorkScheduler, verification evaluation
      to verification.VerificationEvaluator, submission gating to
      submit.SubmissionCoordinator, and blame or failure recording to
      attribution.AttributionCoordinator.
    - Aggregates each dispatched control action into a
      coordinate.ControlDispatchOutcome whose remaining open targets are read back from
      the internal session node state dictionary.
    """

    @property
    @override
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        """Retrieves nodes currently in OPEN state.

        GROUNDING:
        - Grounded via the internal session node state dictionary, filtering for the
          dag_storage.DagNode entries whose tracked coordinate.TargetState is OPEN.
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
        state: coordinate.TargetState = coordinate.TargetState.OPEN,
    ) -> None:
        """Registers a target node with an alias and initial state.

        GROUNDING:
        - Mutates the internal session node state dictionary by inserting the supplied
          dag_storage.DagNode against the supplied coordinate.TargetState.
        - Normalizes the supplied alias string through file_alias.AliasManager.to_alias,
          indexing the resulting file_alias.FileAlias.relative_path text against the
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
          dag_storage.DagNode tracked as coordinate.TargetState.OPEN when a single open
          target remains, and via filesystem modification timestamps of the registered
          file_alias.BoundFile.workspace_path files when multiple open targets remain,
          honoring the caller-supplied last accessed file when provided.
        """
        ...

    @operation
    @override
    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]:
        """Resolves a DagNode instance from a string alias.

        GROUNDING:
        - Resolves the alias string through file_alias.AliasManager.to_alias and looks the
          resulting file_alias.FileAlias.relative_path text up in the internal alias lookup
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
          file aliases via node_config.NodeConfig source file aliases, configured blame
          targets, read-only/read-write paths, or configured role source patterns.
        """
        ...

    @operation
    @override
    def dispatch_get_work(
        self,
        subgraph: Optional[subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> work_scheduler.WorkSchedule:
        """Dispatches work discovery to the work scheduler.

        GROUNDING:
        - Grounded via work_scheduler.WorkScheduler.schedule_work with the supplied
          subgraph.DagSubgraph, directory scope, and maximum batch size, returning the
          discovered work_scheduler.WorkSchedule.
        - Populates the internal session node state dictionary by registering each scheduled
          work_scheduler.ScheduledTask.node as coordinate.TargetState.OPEN.
        - Synchronizes the active session nodes by passing the resulting open target sequence to
          node_config.RoleConfig.set_nodes.
        """
        ...

    @operation
    @override
    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> verification.VerificationResult:
        """Dispatches verification evaluation for a target or all open targets.

        GROUNDING:
        - Grounded via default target resolution to obtain the target dag_storage.DagNode, falling
          back to the sole open node when a supplied alias does not resolve directly in a
          single-open session, then evaluating each requested target through
          verification.VerificationEvaluator.evaluate_verification and combining the
          per-target verification.VerificationResult values into the returned result.
        - Grounded via the internal session node state dictionary to evaluate every
          coordinate.TargetState.OPEN target when the target alias is omitted.
        """
        ...

    @operation
    @override
    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> coordinate.ControlDispatchOutcome:
        """Dispatches submission gating for a target.

        GROUNDING:
        - Grounded via default target resolution and
          submit.SubmissionCoordinator.submit_target for the resolved
          dag_storage.DagNode with the supplied change summary and modification flag, falling
          back to the sole open node when a supplied alias does not resolve directly in a
          single-open session, and updating the internal session node state entry to
          coordinate.TargetState.CLEAN when the submission is accepted.
        """
        ...

    @operation
    @override
    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> coordinate.ControlDispatchOutcome:
        """Dispatches upstream defect attribution.

        GROUNDING:
        - Grounded via default target resolution and matching the blame target alias against
          configured upstream blame targets via attribution.AttributionCoordinator.match_blame_target,
          registering the attributed upstream node in the session coordinator, guarding against
          self-blame, and invoking attribution.AttributionCoordinator.blame_target with the
          supplied explanation, updating the internal session node state entries to record the
          source node as coordinate.TargetState.ATTRIBUTED and the affected dependent nodes
          as coordinate.TargetState.FAILED.
        """
        ...

    @operation
    @override
    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> coordinate.ControlDispatchOutcome:
        """Dispatches failure recording for a target.

        GROUNDING:
        - Grounded via default target resolution and
          attribution.AttributionCoordinator.fail_target for the resolved
          dag_storage.DagNode with the supplied explanation, falling back to the sole open node
          when a supplied alias does not resolve directly in a single-open session, updating the
          internal session node state entries to record the failing target node itself as
          coordinate.TargetState.FAILED and the affected dependent nodes as
          coordinate.TargetState.FAILED.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:46Z
# LAST_CHANGED: 2026-10-11T04:40:32Z
# CHANGE: Record the failing target's own FAILED state when dispatching fail
# SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
# --- END CLEANROOM METADATA ---
