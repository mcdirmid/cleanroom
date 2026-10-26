"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SessionCoordinator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.control.lib.coordinate import (
    ControlDispatchOutcome,
    SessionCoordinator,
    TargetState,
)
from update_with_ai.parts.control.lib.verification import VerificationResult
from update_with_ai.parts.control.lib.work_scheduler import ScheduledTask, WorkSchedule
from update_with_ai.parts.dag.lib import dag_storage, subgraph
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress


@dataclass
class SessionCoordinatorState:
    """Canonical model state for SessionCoordinator."""
    node_states: PretenseDict[DagNode, TargetState] = field(default_factory=PretenseDict)
    node_to_alias: PretenseDict[DagNode, str] = field(default_factory=PretenseDict)
    alias_to_node: PretenseDict[str, DagNode] = field(default_factory=PretenseDict)
    verification_passed: bool = True
    tasks: List[ScheduledTask] = field(default_factory=list)


proto = StateMachineProto[SessionCoordinatorState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_session_node(): pass

@seed_session_node.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
    alias: str | NotBoundType = NotBound,
    target_state: TargetState | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, str, TargetState]]:
    n = DagNode(UnitAddress("core"), RoleAddress("lib")) if isinstance(node, NotBoundType) else node
    a = "lib/core.py" if isinstance(alias, NotBoundType) else str(alias)
    s = TargetState.OPEN if isinstance(target_state, NotBoundType) else target_state
    return (n, a, s)

@seed_session_node.provide
def _(
    state: SessionCoordinatorState,
    this: Any,
    node: DagNode,
    alias: str,
    target_state: TargetState,
    result: None = None,
) -> None:
    state.node_states[node] = target_state
    state.node_to_alias[node] = alias
    state.alias_to_node[alias] = node


# ==============================================================================
# 2. SessionCoordinator Transitions
# ==============================================================================

@proto.transition(name="open_targets")
def open_targets(): pass

@open_targets.returns
def _(state: SessionCoordinatorState, this: Any, outcome: object = NotBound) -> Optional[Outcome[Sequence[DagNode]]]:
    expected = tuple(n for n, s in state.node_states.items() if s == TargetState.OPEN)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(SessionCoordinator.register_node)
def register_node(): pass

@register_node.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
    alias: str | NotBoundType = NotBound,
    target_state: TargetState | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode, str, TargetState]]:
    n = DagNode(UnitAddress("mod"), RoleAddress("lib")) if isinstance(node, NotBoundType) else node
    a = "lib/mod.py" if isinstance(alias, NotBoundType) else str(alias)
    s = TargetState.OPEN if isinstance(target_state, NotBoundType) else target_state
    return (n, a, s)

@register_node.provide
def _(
    state: SessionCoordinatorState,
    this: Any,
    node: DagNode,
    alias: str,
    target_state: TargetState,
    result: None = None,
) -> None:
    state.node_states[node] = target_state
    state.node_to_alias[node] = alias
    state.alias_to_node[alias] = node


@proto.transition(SessionCoordinator.reset_nodes)
def reset_nodes(): pass

@reset_nodes.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    nodes: Sequence[DagNode] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[DagNode]]]:
    ns = () if isinstance(nodes, NotBoundType) else tuple(nodes)
    return (ns,)

@reset_nodes.provide
def _(
    state: SessionCoordinatorState,
    this: Any,
    nodes: Sequence[DagNode],
    result: None = None,
) -> None:
    state.node_states.clear()
    state.node_to_alias.clear()
    state.alias_to_node.clear()
    for n in nodes:
        alias = f"{n.role_address}/{n.unit_address}.py"
        state.node_states[n] = TargetState.OPEN
        state.node_to_alias[n] = alias
        state.alias_to_node[alias] = n


@proto.transition(SessionCoordinator.resolve_default_target)
def resolve_default_target(): pass

@resolve_default_target.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    last_accessed_file: Optional[Any] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[Any]]]:
    f = None if isinstance(last_accessed_file, NotBoundType) else last_accessed_file
    return (f,)

@resolve_default_target.returns
def _(
    state: SessionCoordinatorState,
    this: Any,
    last_accessed_file: Optional[Any],
    outcome: object = NotBound,
) -> Optional[Outcome[Optional[DagNode]]]:
    open_nodes = [n for n, s in state.node_states.items() if s == TargetState.OPEN]
    expected = open_nodes[0] if len(open_nodes) == 1 else None
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(SessionCoordinator.get_node_for_alias)
def get_node_for_alias(): pass

@get_node_for_alias.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    alias: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    a = "lib/core.py" if isinstance(alias, NotBoundType) else str(alias)
    return (a,)

@get_node_for_alias.returns
def _(
    state: SessionCoordinatorState,
    this: Any,
    alias: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Optional[DagNode]]]:
    expected = state.alias_to_node.get(alias)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(SessionCoordinator.get_alias_for_node)
def get_alias_for_node(): pass

@get_alias_for_node.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    node: DagNode | NotBoundType = NotBound,
) -> Optional[Tuple[DagNode]]:
    if isinstance(node, NotBoundType):
        if not state.node_to_alias:
            return None
        return (next(iter(state.node_to_alias.keys())),)
    return (node,)

@get_alias_for_node.returns
def _(
    state: SessionCoordinatorState,
    this: Any,
    node: DagNode,
    outcome: object = NotBound,
) -> Optional[Outcome[str]]:
    expected = state.node_to_alias.get(node, f"{node.role_address}/{node.unit_address}")
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(SessionCoordinator.dispatch_get_work)
def dispatch_get_work(): pass

@dispatch_get_work.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    subgraph: Optional[subgraph.DagSubgraph] | NotBoundType = NotBound,
    dir_scope: Optional[str] | NotBoundType = NotBound,
    max_batch_size: Optional[int] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[subgraph.DagSubgraph], Optional[str], Optional[int]]]:
    sg = None if isinstance(subgraph, NotBoundType) else subgraph
    ds = None if isinstance(dir_scope, NotBoundType) else dir_scope
    mb = None if isinstance(max_batch_size, NotBoundType) else max_batch_size
    return (sg, ds, mb)

@dispatch_get_work.returns
def _(
    state: SessionCoordinatorState,
    this: Any,
    subgraph: Optional[subgraph.DagSubgraph],
    dir_scope: Optional[str],
    max_batch_size: Optional[int],
    outcome: object = NotBound,
) -> Optional[Outcome[WorkSchedule]]:
    expected = WorkSchedule(tasks=tuple(state.tasks))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(SessionCoordinator.dispatch_check_files)
def dispatch_check_files(): pass

@dispatch_check_files.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    target_alias: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str]]]:
    ta = None if isinstance(target_alias, NotBoundType) else target_alias
    return (ta,)

@dispatch_check_files.returns
def _(
    state: SessionCoordinatorState,
    this: Any,
    target_alias: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[VerificationResult]]:
    expected = VerificationResult(
        passed=state.verification_passed,
        diagnostic_output="All checks passed." if state.verification_passed else "Verification failed.",
    )
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(SessionCoordinator.dispatch_submit)
def dispatch_submit(): pass

@dispatch_submit.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    target_alias: Optional[str] | NotBoundType = NotBound,
    change_summary: Optional[str] | NotBoundType = NotBound,
    has_modifications: bool | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str], Optional[str], bool]]:
    ta = None if isinstance(target_alias, NotBoundType) else target_alias
    cs = "Change" if isinstance(change_summary, NotBoundType) else change_summary
    hm = True if isinstance(has_modifications, NotBoundType) else bool(has_modifications)
    return (ta, cs, hm)

@dispatch_submit.returns
def _(
    state: SessionCoordinatorState,
    this: Any,
    target_alias: Optional[str],
    change_summary: Optional[str],
    has_modifications: bool,
    outcome: object = NotBound,
) -> Optional[Outcome[ControlDispatchOutcome]]:
    node = state.alias_to_node.get(target_alias or "")
    if not node:
        open_nodes = [n for n, s in state.node_states.items() if s == TargetState.OPEN]
        node = open_nodes[0] if len(open_nodes) == 1 else None

    if node is None:
        expected = ControlDispatchOutcome(
            success=False,
            message="No target node resolved for submission.",
            remaining_open_targets=tuple(n for n, s in state.node_states.items() if s == TargetState.OPEN),
        )
    elif not state.verification_passed:
        expected = ControlDispatchOutcome(
            success=False,
            message="Verification checks failed for target.",
            remaining_open_targets=tuple(n for n, s in state.node_states.items() if s == TargetState.OPEN),
        )
    else:
        rem = tuple(n for n, s in state.node_states.items() if s == TargetState.OPEN and n != node)
        expected = ControlDispatchOutcome(
            success=True,
            message=f"Submitted target {node} successfully.",
            remaining_open_targets=rem,
        )

    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@dispatch_submit.provide
def _(
    state: SessionCoordinatorState,
    this: Any,
    target_alias: Optional[str],
    change_summary: Optional[str],
    has_modifications: bool,
    result: ControlDispatchOutcome,
) -> None:
    if result.success:
        node = state.alias_to_node.get(target_alias or "")
        if not node:
            open_nodes = [n for n, s in state.node_states.items() if s == TargetState.OPEN]
            node = open_nodes[0] if len(open_nodes) == 1 else None
        if node:
            state.node_states[node] = TargetState.CLEAN


@proto.transition(SessionCoordinator.dispatch_blame)
def dispatch_blame(): pass

@dispatch_blame.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    source_alias: Optional[str] | NotBoundType = NotBound,
    blame_target_alias: Optional[str] | NotBoundType = NotBound,
    explanation: str | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str], Optional[str], str]]:
    sa = None if isinstance(source_alias, NotBoundType) else source_alias
    ta = "lib/core.py" if isinstance(blame_target_alias, NotBoundType) else str(blame_target_alias)
    exp = "Defect found" if isinstance(explanation, NotBoundType) else str(explanation)
    return (sa, ta, exp)

@dispatch_blame.returns
def _(
    state: SessionCoordinatorState,
    this: Any,
    source_alias: Optional[str],
    blame_target_alias: Optional[str],
    explanation: str,
    outcome: object = NotBound,
) -> Optional[Outcome[ControlDispatchOutcome]]:
    if "\n" in explanation.strip():
        expected = ControlDispatchOutcome(
            success=False,
            message="Critique must be a single paragraph without newline characters.",
            remaining_open_targets=tuple(n for n, s in state.node_states.items() if s == TargetState.OPEN),
        )
    else:
        expected = ControlDispatchOutcome(
            success=True,
            message=f"Blame recorded for {blame_target_alias}.",
            remaining_open_targets=(),
        )
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(SessionCoordinator.dispatch_fail)
def dispatch_fail(): pass

@dispatch_fail.arguments
def _(
    state: SessionCoordinatorState,
    this: Any,
    target_alias: Optional[str] | NotBoundType = NotBound,
    reason: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str], Optional[str]]]:
    ta = None if isinstance(target_alias, NotBoundType) else target_alias
    r = "Unrecoverable error" if isinstance(reason, NotBoundType) or reason is None else str(reason)
    return (ta, r)

@dispatch_fail.returns
def _(
    state: SessionCoordinatorState,
    this: Any,
    target_alias: Optional[str],
    reason: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[ControlDispatchOutcome]]:
    expected = ControlDispatchOutcome(
        success=True,
        message=f"Target failure recorded: {reason}",
        remaining_open_targets=(),
    )
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@dispatch_fail.provide
def _(
    state: SessionCoordinatorState,
    this: Any,
    target_alias: Optional[str],
    reason: Optional[str],
    result: ControlDispatchOutcome,
) -> None:
    for n in state.node_states:
        state.node_states[n] = TargetState.FAILED


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_session_coordinator_fake(state: Optional[SessionCoordinatorState] = None) -> SessionCoordinator:
    """Instantiate a synthesized SessionCoordinator fake."""
    st = state or SessionCoordinatorState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(SessionCoordinator)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

import os
import tempfile
from update_with_ai.parts.control.lib import (
    attribution,
    coordinate_impl,
    submit,
    verification,
    work_scheduler,
)
from update_with_ai.parts.agent.lib import file_alias, node_config
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton
from update_with_ai.parts.agent.lib.session import agent_session
from update_with_ai.parts.core.lib import file_paths


class MockDagStorageCoordinate:
    tier = agent_session

    def __init__(self) -> None:
        self.dependencies: Dict[DagNode, List[Any]] = {}
        self.materialized: List[DagNode] = []

    def get_dependencies(self, node: DagNode) -> List[Any]:
        return self.dependencies.get(node, [])

    def materialize_template(self, node: DagNode) -> None:
        self.materialized.append(node)


class MockRoleConfigCoordinate:
    tier = agent_session

    def __init__(self) -> None:
        self.nodes: Sequence[DagNode] = []

    def set_nodes(self, nodes: Sequence[DagNode]) -> None:
        self.nodes = list(nodes)


class MockWorkSchedulerCoordinate:
    tier = agent_session

    def __init__(self) -> None:
        self.tasks_to_schedule: List[Any] = []

    def schedule_work(self, subgraph: Any = None, dir_scope: Any = None, max_batch_size: Any = None) -> work_scheduler.WorkSchedule:
        return work_scheduler.WorkSchedule(tasks=self.tasks_to_schedule)


class MockVerificationEvaluatorCoordinate:
    tier = agent_session

    def __init__(self) -> None:
        self.passed = True
        self.diagnostic = ""
        self.is_cached = False

    def evaluate_verification(self, target: Optional[DagNode] = None) -> verification.VerificationResult:
        return verification.VerificationResult(
            passed=self.passed,
            diagnostic_output=self.diagnostic,
            is_cached=self.is_cached,
        )


class MockSubmissionCoordinatorCoordinate:
    tier = agent_session

    def __init__(self) -> None:
        self.accepted = True
        self.message = "Submission accepted"

    def submit_target(self, target_node: Any, change_summary: Any = None, has_modifications: bool = False, in_batch_dependencies: Any = None) -> Any:
        @dataclass
        class Res:
            accepted: bool
            message: str
        return Res(accepted=self.accepted, message=self.message)


class MockAttributionCoordinatorCoordinate:
    tier = agent_session

    def __init__(self) -> None:
        self.accepted = True
        self.message = "Attribution accepted"
        self.affected: List[DagNode] = []

    def match_blame_target(self, source_node: Any, val: Any, val_str: str) -> Optional[Any]:
        return None

    def blame_target(self, source_node: Any, blame_target_node: Any, explanation: str, in_batch_dependencies: Any = None, in_batch_dependents: Any = None) -> Any:
        @dataclass
        class Res:
            accepted: bool
            message: str
            affected_nodes: Sequence[DagNode]
        return Res(accepted=self.accepted, message=self.message, affected_nodes=self.affected)

    def fail_target(self, target_node: Any, explanation: str, in_batch_dependents: Any = None) -> Any:
        @dataclass
        class Res:
            accepted: bool
            message: str
            affected_nodes: Sequence[DagNode]
        return Res(accepted=self.accepted, message=self.message, affected_nodes=self.affected)


class MockNodeConfigCoordinate:
    tier = agent_session

    def __init__(self) -> None:
        self.src_file_alias_by_node: Dict[DagNode, str] = {}
        self.read_write_files: List[Any] = []
        self.read_only_files: List[Any] = []
        self.blame_targets_by_node: Dict[DagNode, Set[Any]] = {}


class MockAliasManagerCoordinate:
    tier = agent_session

    def to_alias(self, path: str) -> Any:
        return file_alias.FileAlias(file_alias.RelativePath(path))


class TestCoordinateImplReal(unittest.TestCase):
    """Direct unit tests for coordinate_impl.SessionCoordinator."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        coordinate_impl.__initialize__(self.registry)

        self.mock_storage = MockDagStorageCoordinate()
        self.mock_role_cfg = MockRoleConfigCoordinate()
        self.mock_node_cfg = MockNodeConfigCoordinate()
        self.mock_alias_mgr = MockAliasManagerCoordinate()
        self.mock_scheduler = MockWorkSchedulerCoordinate()
        self.mock_verifier = MockVerificationEvaluatorCoordinate()
        self.mock_submitter = MockSubmissionCoordinatorCoordinate()
        self.mock_attributor = MockAttributionCoordinatorCoordinate()

        self.registry.register_instance(self.mock_storage, keys=[dag_storage.DagStorage], tier=agent_session)
        self.registry.register_instance(self.mock_role_cfg, keys=[node_config.RoleConfig], tier=agent_session)
        self.registry.register_instance(self.mock_node_cfg, keys=[node_config.NodeConfig], tier=agent_session)
        self.registry.register_instance(self.mock_alias_mgr, keys=[file_alias.AliasManager], tier=agent_session)
        self.registry.register_instance(self.mock_scheduler, keys=[work_scheduler.WorkScheduler], tier=agent_session)
        self.registry.register_instance(self.mock_verifier, keys=[verification.VerificationEvaluator], tier=agent_session)
        self.registry.register_instance(self.mock_submitter, keys=[submit.SubmissionCoordinator], tier=agent_session)
        self.registry.register_instance(self.mock_attributor, keys=[attribution.AttributionCoordinator], tier=agent_session)

        self.node1 = DagNode(UnitAddress("pkg:calc"), RoleAddress("lib"))
        self.node2 = DagNode(UnitAddress("pkg:calc"), RoleAddress("test"))

    def test_registration_and_open_targets(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(coordinate_impl.SessionCoordinator)
            coord.register_node(self.node1, "pkg/lib/calc.py")
            self.assertEqual(coord.open_targets, [self.node1])

            # Synthetic //session:target filtered out on subsequent node registration
            synthetic = DagNode(UnitAddress("//session:target"), RoleAddress("lib"))
            coord.register_node(synthetic, "synthetic")
            node3 = DagNode(UnitAddress("pkg:other"), RoleAddress("lib"))
            coord.register_node(node3, "pkg/lib/other.py")
            self.assertNotIn(synthetic, coord.open_targets)
            self.assertIn(node3, coord.open_targets)

            # Change target state to clean
            coord.register_node(self.node1, "pkg/lib/calc.py", state=TargetState.CLEAN)
            self.assertNotIn(self.node1, coord.open_targets)

    def test_get_node_for_alias_and_matching(self) -> None:
        node_unique = DagNode(UnitAddress("pkg:other"), RoleAddress("test"))
        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(coordinate_impl.SessionCoordinator)
            coord.reset_nodes([self.node1, node_unique])

            # Direct unique unit match
            self.assertEqual(coord.get_node_for_alias("calc"), self.node1)
            self.assertEqual(coord.get_node_for_alias("other"), node_unique)

            # File proxy match: lib role
            self.assertEqual(coord.get_node_for_alias("pkg/lib/calc.py"), self.node1)

            # File proxy match: test role
            self.assertEqual(coord.get_node_for_alias("pkg/tests/other_test.py"), node_unique)

            # Empty alias -> None
            self.assertIsNone(coord.get_node_for_alias(""))
            self.assertIsNone(coord.get_node_for_alias("nonexistent"))

    def test_resolve_default_target(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(coordinate_impl.SessionCoordinator)

            # 1. No open targets -> None
            self.assertIsNone(coord.resolve_default_target())

            # 2. Single open target -> returns it
            coord.register_node(self.node1, "pkg/lib/calc.py")
            self.assertEqual(coord.resolve_default_target(), self.node1)

            # 3. Multiple open targets -> disambiguate via last_accessed_file
            coord.register_node(self.node2, "pkg/tests/calc_test.py")
            self.assertEqual(coord.resolve_default_target(last_accessed_file="pkg/tests/calc_test.py"), self.node2)

    def test_dispatch_get_work(self) -> None:
        task1 = work_scheduler.ScheduledTask(
            node=self.node1,
            task_prompt="Prompt 1",
            dependency_paths=[],
            feedback_messages=[],
        )
        self.mock_scheduler.tasks_to_schedule = [task1]

        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(coordinate_impl.SessionCoordinator)
            schedule = coord.dispatch_get_work()
            self.assertEqual(len(schedule.tasks), 1)
            self.assertIn(self.node1, coord.open_targets)
            self.assertIn(self.node1, self.mock_storage.materialized)
            self.assertEqual(self.mock_role_cfg.nodes, [self.node1])

    def test_dispatch_check_files(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(coordinate_impl.SessionCoordinator)
            coord.register_node(self.node1, "pkg/lib/calc.py")

            # Check specific target
            res = coord.dispatch_check_files("pkg/lib/calc.py")
            self.assertTrue(res.passed)

            # Check all open targets
            res_all = coord.dispatch_check_files()
            self.assertTrue(res_all.passed)
            self.assertIn("verified successfully", res_all.diagnostic_output)

    def test_dispatch_submit_lifecycle(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(coordinate_impl.SessionCoordinator)
            coord.register_node(self.node1, "pkg/lib/calc.py")
            coord.register_node(self.node2, "pkg/tests/calc_test.py")

            # Submitting unknown target fails when multiple open targets exist
            res = coord.dispatch_submit("unknown.py")
            self.assertFalse(res.success)
            self.assertIn("not an open target", res.message)

            # Submitting valid target succeeds
            res = coord.dispatch_submit("pkg/lib/calc.py", change_summary="Added calc")
            self.assertTrue(res.success)
            self.assertEqual(coord.open_targets, [self.node2])

    def test_dispatch_blame_lifecycle(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(coordinate_impl.SessionCoordinator)
            coord.register_node(self.node1, "pkg/lib/calc.py")
            coord.register_node(self.node2, "pkg/tests/calc_test.py")

            # Self blame rejected
            res = coord.dispatch_blame("pkg/tests/calc_test.py", "pkg/tests/calc_test.py", "Self blame")
            self.assertFalse(res.success)

            # Valid blame
            self.mock_attributor.affected = [self.node2]
            res = coord.dispatch_blame("pkg/tests/calc_test.py", "pkg/lib/calc.py", "Upstream contract bug")
            self.assertTrue(res.success)

    def test_dispatch_fail_lifecycle(self) -> None:
        with enter_phase(agent_session, registry=self.registry) as scope:
            coord = scope.get_singleton(coordinate_impl.SessionCoordinator)
            coord.register_node(self.node1, "pkg/lib/calc.py")

            self.mock_attributor.affected = [self.node1]
            res = coord.dispatch_fail("pkg/lib/calc.py", "Unresolvable defect")
            self.assertTrue(res.success)
            self.assertEqual(coord.open_targets, [])

    def test_helpers(self) -> None:
        with enter_phase(agent_session, registry=self.registry):
            p, u = coordinate_impl._extract_unit_info(self.node1)
            self.assertEqual(p, "pkg")
            self.assertEqual(u, "calc")

            norm = coordinate_impl._normalize_alias("/some/path.py")
            self.assertEqual(norm, "/some/path.py")

            alias = coordinate_impl._node_display_alias(self.node1)
            self.assertTrue("calc" in alias)


class TestSessionCoordinatorUnit(unittest.TestCase):
    """Unit tests for synthesized SessionCoordinator fake."""

    def setUp(self) -> None:
        self.state = SessionCoordinatorState()
        self.sm = proto.make_state_machine(self.state)
        self.node = DagNode(UnitAddress("core"), RoleAddress("lib"))
        self.sm.seed_session_node(self.node, "lib/core.py", TargetState.OPEN)
        self.fake: SessionCoordinator = self.sm.as_fake(SessionCoordinator)

    def test_open_targets(self) -> None:
        self.assertEqual(self.fake.open_targets, (self.node,))

    def test_resolve_default_target(self) -> None:
        self.assertEqual(self.fake.resolve_default_target(), self.node)

    def test_get_node_for_alias(self) -> None:
        self.assertEqual(self.fake.get_node_for_alias("lib/core.py"), self.node)
        self.assertIsNone(self.fake.get_node_for_alias("unknown.py"))

    def test_dispatch_submit_success(self) -> None:
        outcome = self.fake.dispatch_submit("lib/core.py", "Implemented core")
        self.assertTrue(outcome.success)
        self.assertEqual(outcome.remaining_open_targets, ())
        self.assertEqual(self.fake.open_targets, ())

    def test_dispatch_fail(self) -> None:
        outcome = self.fake.dispatch_fail("lib/core.py", "Timeout exceeded")
        self.assertTrue(outcome.success)
        self.assertEqual(self.state.node_states[self.node], TargetState.FAILED)


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestSessionCoordinatorFuzz(unittest.TestCase):
    """Property fuzz testing for SessionCoordinator."""

    @settings(max_examples=30)
    @given(
        count=st.integers(min_value=1, max_value=6),
    )
    def test_node_registration_and_open_target_invariants(self, count: int) -> None:
        state = SessionCoordinatorState()
        sm = proto.make_state_machine(state)
        nodes = [DagNode(UnitAddress(f"unit_{i}"), RoleAddress("lib")) for i in range(count)]
        for i, n in enumerate(nodes):
            sm.seed_session_node(n, f"alias_{i}", TargetState.OPEN)

        fake = sm.as_fake(SessionCoordinator)
        self.assertEqual(len(fake.open_targets), count)

        # Submitting the first node reduces open targets by 1
        outcome = fake.dispatch_submit("alias_0", "Submitted first node")
        self.assertTrue(outcome.success)
        self.assertEqual(len(fake.open_targets), count - 1)
