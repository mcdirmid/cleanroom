# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:03:56Z
# CHANGE: Remove a stray blank line from the coordinator protocol body
# CODE_HASH: 52d01a6fc2ea
# --- END CLEANROOM METADATA ---

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol, Sequence
from update_with_ai.parts.dag.lib import dag_storage, dag_subgraph
from . import (
    control_attribution,
    control_submit,
    control_verification,
    control_work_scheduler,
)


class TargetState(str, Enum):
    """Lifecycle state of an active target node within the session."""

    OPEN = "OPEN"
    CLEAN = "CLEAN"
    FAILED = "FAILED"
    ATTRIBUTED = "ATTRIBUTED"


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


class SessionCoordinator(Protocol):
    """Central coordinator facade managing session state and dispatching actions."""

    # Contract: Sequence of nodes currently in OPEN state.
    @property
    def open_targets(self) -> Sequence[dag_storage.DagNode]: ...

    # Contract: Registers a target node in the session with alias and target state.
    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: TargetState = TargetState.OPEN,
    ) -> None: ...

    # Contract: Resets session node tracking to specified nodes, replacing open targets.
    def reset_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None: ...

    # Contract: Resolves default target node; selects sole open target or disambiguates by last accessed file.
    def resolve_default_target(
        self, last_accessed_file: Optional[Any] = None
    ) -> Optional[dag_storage.DagNode]: ...

    # Contract: Looks up a registered node by its file alias string.
    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]: ...

    # Contract: Looks up the primary file alias string for a registered node.
    def get_alias_for_node(self, node: dag_storage.DagNode) -> str: ...

    # Contract: Dispatches work discovery and registers discovered nodes as open targets.
    def dispatch_get_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule: ...

    # Contract: Dispatches verification check evaluation for a target or all open targets.
    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> control_verification.VerificationResult: ...

    # Contract: Dispatches submission gating and clean target resolution.
    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> ControlDispatchOutcome: ...

    # Contract: Dispatches defect attribution to an upstream dependency.
    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> ControlDispatchOutcome: ...

    # Contract: Dispatches task failure recording.
    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> ControlDispatchOutcome: ...
