"""Low-level implementation specification for control_coordinate_impl."""

from typing import Optional, Sequence
from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import control_coordinate
import control_verification
import control_work_scheduler
import dag_storage
import dag_subgraph


@singleton_type("agent_session")
class SessionCoordinator(
    control_coordinate.SessionCoordinator,
    InTier[AgentSessionTier],
):
    """Implementation of session coordinator facade."""

    @property
    @override
    def open_targets(self) -> Sequence[dag_storage.DagNode]:
        ...

    @operation
    @override
    def register_node(
        self,
        node: dag_storage.DagNode,
        alias: str,
        state: control_coordinate.TargetState = control_coordinate.TargetState.OPEN,
    ) -> None:
        ...

    @operation
    @override
    def resolve_default_target(self) -> Optional[dag_storage.DagNode]:
        ...

    @operation
    @override
    def get_node_for_alias(self, alias: str) -> Optional[dag_storage.DagNode]:
        ...

    @operation
    @override
    def get_alias_for_node(self, node: dag_storage.DagNode) -> str:
        ...

    @operation
    @override
    def dispatch_get_work(
        self,
        subgraph: Optional[dag_subgraph.DagSubgraph] = None,
        dir_scope: Optional[str] = None,
        max_batch_size: Optional[int] = None,
    ) -> control_work_scheduler.WorkSchedule:
        ...

    @operation
    @override
    def dispatch_check_files(
        self, target_alias: Optional[str] = None
    ) -> control_verification.VerificationResult:
        ...

    @operation
    @override
    def dispatch_submit(
        self,
        target_alias: Optional[str] = None,
        change_summary: Optional[str] = None,
        has_modifications: bool = False,
    ) -> control_coordinate.ControlDispatchOutcome:
        ...

    @operation
    @override
    def dispatch_blame(
        self,
        source_alias: Optional[str] = None,
        blame_target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        ...

    @operation
    @override
    def dispatch_fail(
        self,
        target_alias: Optional[str] = None,
        explanation: str = "",
    ) -> control_coordinate.ControlDispatchOutcome:
        ...
