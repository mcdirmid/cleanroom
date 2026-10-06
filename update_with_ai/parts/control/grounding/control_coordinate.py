"""Grounding specification for control_coordinate."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Sequence
from support.lib.grounding_support import AgentSessionTier, InTier
from parts.dag.grounding import dag_storage, dag_subgraph
from . import control_attribution, control_submit, control_verification, control_work_scheduler

__all__ = ["TargetState", "ControlDispatchOutcome", "SessionCoordinator"]


class TargetState(str, Enum):
    OPEN = "OPEN"
    CLEAN = "CLEAN"
    FAILED = "FAILED"
    ATTRIBUTED = "ATTRIBUTED"


@dataclass(frozen=True)
class ControlDispatchOutcome:
    success: bool
    message: str
    remaining_open_targets: Sequence[dag_storage.DagNode]


class SessionCoordinator(InTier[AgentSessionTier], Protocol):
    @property
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        """
        DEFERRED:
        - Sequence of nodes currently in OPEN state.
        """
        raise NotImplementedError

    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: TargetState = TargetState.OPEN,
    ) -> None:
        """
        DEFERRED:
        - Registers a target node in the session.
        """
        raise NotImplementedError

    def resolve_default_target(self) -> Optional[dag_storage.DagNode]:
        """
        DEFERRED:
        - Resolves the default target node when omitted by the caller.
        """
        raise NotImplementedError

    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]:
        """
        DEFERRED:
        - Looks up a registered node by its file alias string.
        """
        raise NotImplementedError

    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        """
        DEFERRED:
        - Looks up the primary file alias string for a registered node.
        """
        raise NotImplementedError

    def dispatch_get_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule:
        """
        DEFERRED:
        - Dispatches work discovery and registers discovered nodes as open targets.
        """
        raise NotImplementedError

    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> control_verification.VerificationResult:
        """
        DEFERRED:
        - Dispatches verification check evaluation for a target or all open targets.
        """
        raise NotImplementedError

    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> ControlDispatchOutcome:
        """
        DEFERRED:
        - Dispatches submission gating and clean target resolution.
        """
        raise NotImplementedError

    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> ControlDispatchOutcome:
        """
        DEFERRED:
        - Dispatches defect attribution to an upstream dependency.
        """
        raise NotImplementedError

    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> ControlDispatchOutcome:
        """
        DEFERRED:
        - Dispatches task failure recording.
        """
        raise NotImplementedError
