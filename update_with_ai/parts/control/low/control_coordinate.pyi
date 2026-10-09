# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-07T00:11:26Z
# CHANGE: new file
# CODE_HASH: 0420d4f97c75
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Low-level interface specification for control_coordinate."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, Sequence
from framework import data_type, operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import control_attribution
import control_submit
import control_verification
import control_work_scheduler
import dag_storage
import dag_subgraph


class TargetState(str, Enum):
    """Lifecycle state of an active target node within the session."""

    OPEN = "OPEN"
    CLEAN = "CLEAN"
    FAILED = "FAILED"
    ATTRIBUTED = "ATTRIBUTED"


@data_type
@dataclass(frozen=True)
class ControlDispatchOutcome:
    """Outcome of a dispatched control action.

    Args:
        success: True if operation succeeded.
        message: Diagnostic output or status message.
        remaining_open_targets: Sequence of remaining open target nodes.
    """

    success: bool
    message: str
    remaining_open_targets: Sequence[dag_storage.DagNode]


@singleton_type("agent_session")
class SessionCoordinator(InTier[AgentSessionTier], Protocol):
    """Central coordinator facade managing session state and dispatching actions."""

    @property
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        """Sequence of nodes currently in OPEN state."""
        ...

    @operation
    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: TargetState = TargetState.OPEN,
    ) -> None:
        """Registers a target node in the session."""
        ...

    @operation
    def reset_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None:
        """Resets session node tracking to specified nodes.

        POSTCONDITIONS:
        - Replaces internal open targets with provided nodes.
        """
        ...

    @operation
    def resolve_default_target(
        self, last_accessed_file: Optional[Any] = None
    ) -> Optional[dag_storage.DagNode]:
        """Resolves the default target node when omitted by the caller.

        POSTCONDITIONS:
        - Resolves single open target or disambiguates by last accessed file.
        """
        ...


    @operation
    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]:
        """Looks up a registered node by its file alias string."""
        ...

    @operation
    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        """Looks up the primary file alias string for a registered node."""
        ...

    @operation
    def dispatch_get_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule:
        """Dispatches work discovery and registers discovered nodes as open targets."""
        ...

    @operation
    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> control_verification.VerificationResult:
        """Dispatches verification check evaluation for a target or all open targets."""
        ...

    @operation
    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> ControlDispatchOutcome:
        """Dispatches submission gating and clean target resolution."""
        ...

    @operation
    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> ControlDispatchOutcome:
        """Dispatches defect attribution to an upstream dependency."""
        ...

    @operation
    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> ControlDispatchOutcome:
        """Dispatches task failure recording."""
        ...
