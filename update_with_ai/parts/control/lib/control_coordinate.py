# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-06T10:45:00Z
# CHANGE: new file
# CODE_HASH: 6f13bea190bc
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

    @property
    def open_targets(self) -> Sequence[dag_storage.DagNode]: ...

    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: TargetState = TargetState.OPEN,
    ) -> None: ...

    def reset_nodes(self, nodes: Sequence[dag_storage.DagNode]) -> None: ...

    def resolve_default_target(
        self, last_accessed_file: Optional[Any] = None
    ) -> Optional[dag_storage.DagNode]: ...

    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]: ...


    def get_alias_for_node(self, node: dag_storage.DagNode) -> str: ...

    def dispatch_get_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule: ...

    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> control_verification.VerificationResult: ...

    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> ControlDispatchOutcome: ...

    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> ControlDispatchOutcome: ...

    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> ControlDispatchOutcome: ...
