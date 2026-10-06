"""Grounding specification for control_coordinate_impl."""

from __future__ import annotations
from typing import Optional, Sequence
from support.lib.grounding_support import AgentSessionTier, InTier, only_elem
from parts.dag.grounding import dag_storage, dag_subgraph
from . import (
    control_attribution,
    control_coordinate,
    control_submit,
    control_verification,
    control_work_scheduler,
)

__all__ = ["SessionCoordinator"]


class SessionCoordinator(
    control_coordinate.SessionCoordinator,
    InTier[AgentSessionTier],
):
    """
    DISCHARGED:
    - SessionCoordinator.open_targets
    - SessionCoordinator.register_node
    - SessionCoordinator.resolve_default_target
    - SessionCoordinator.get_node_for_alias
    - SessionCoordinator.get_alias_for_node
    - SessionCoordinator.dispatch_get_work
    - SessionCoordinator.dispatch_check_files
    - SessionCoordinator.dispatch_submit
    - SessionCoordinator.dispatch_blame
    - SessionCoordinator.dispatch_fail
    """

    @property
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        """
        COVERED:
        - Sequence of nodes currently in OPEN state.
        """
        sample_node = dag_storage.DagNode(
            unit_address=dag_storage.UnitAddress("sample"),
            role_address=dag_storage.RoleAddress("sample"),
        )
        nodes: Sequence[dag_storage.DagNode] = [sample_node]
        raise NotImplementedError

    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: control_coordinate.TargetState = control_coordinate.TargetState.OPEN,
    ) -> None:
        """
        COVERED:
        - Registers a target node in the session.
        """
        n = node
        a = alias
        s = state
        raise NotImplementedError

    def resolve_default_target(self) -> Optional[dag_storage.DagNode]:
        """
        COVERED:
        - Resolves the default target node when omitted by the caller.
        """
        open_n = self.open_targets
        picked = only_elem(open_n)
        raise NotImplementedError

    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]:
        """
        COVERED:
        - Looks up a registered node by its file alias string.
        """
        open_n = self.open_targets
        node = only_elem(open_n)
        raise NotImplementedError

    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        """
        COVERED:
        - Looks up the primary file alias string for a registered node.
        """
        n = node
        raise NotImplementedError

    def dispatch_get_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule:
        """
        COVERED:
        - Dispatches work discovery and registers discovered nodes as open targets.
        """
        scheduler = self.get_singleton(control_work_scheduler.WorkScheduler)
        schedule = scheduler.schedule_work(subgraph=subgraph, dir_scope=dir_scope, max_batch_size=max_batch_size)
        raise NotImplementedError

    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> control_verification.VerificationResult:
        """
        COVERED:
        - Dispatches verification check evaluation for a target or all open targets.
        """
        evaluator = self.get_singleton(control_verification.VerificationEvaluator)
        target = self.resolve_default_target()
        res = evaluator.evaluate_verification(target)
        raise NotImplementedError

    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> control_coordinate.ControlDispatchOutcome:
        """
        COVERED:
        - Dispatches submission gating and clean target resolution.
        """
        coordinator = self.get_singleton(control_submit.SubmissionCoordinator)
        target = self.resolve_default_target()
        assert target is not None
        outcome = coordinator.submit_target(target, change_summary, has_modifications)
        disp = control_coordinate.ControlDispatchOutcome(
            success=outcome.accepted,
            message=outcome.message,
            remaining_open_targets=[],
        )
        raise NotImplementedError

    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        """
        COVERED:
        - Dispatches defect attribution to an upstream dependency.
        """
        attribution = self.get_singleton(control_attribution.AttributionCoordinator)
        source = self.resolve_default_target()
        assert source is not None
        outcome = attribution.blame_target(source, source, explanation)
        disp = control_coordinate.ControlDispatchOutcome(
            success=outcome.accepted,
            message=outcome.message,
            remaining_open_targets=[],
        )
        raise NotImplementedError

    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        """
        COVERED:
        - Dispatches task failure recording.
        """
        attribution = self.get_singleton(control_attribution.AttributionCoordinator)
        target = self.resolve_default_target()
        assert target is not None
        outcome = attribution.fail_target(target, explanation)
        disp = control_coordinate.ControlDispatchOutcome(
            success=outcome.accepted,
            message=outcome.message,
            remaining_open_targets=[],
        )
        raise NotImplementedError
