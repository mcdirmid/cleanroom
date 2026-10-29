"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for SessionCoordinator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict, PretenseSet
from pretense import Domain, StateMachine, TransitionContext, transition
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


class SessionCoordinatorStateMachine(StateMachine[SessionCoordinatorState]):
    """Pretense StateMachine for SessionCoordinator."""

    def __init__(self, state: Optional[SessionCoordinatorState] = None):
        super().__init__(state=state or SessionCoordinatorState())

    # ==============================================================================
    # 1. Seeding Transitions
    # ==============================================================================

    @transition.seeding()
    def seed_session_node(
        self,
        ctx: TransitionContext[None, [DagNode, str, TargetState], None],
    ) -> None:
        ctx.arguments(
                    node=Domain(strategy=lambda: DagNode(UnitAddress('core'), RoleAddress('lib'))),
                    alias=Domain(strategy=lambda: 'lib/core.py'),
                    target_state=Domain(strategy=lambda: TargetState.OPEN),
                )
        def _consequent(
            res: None,
            node: DagNode = DagNode(UnitAddress("core"), RoleAddress("lib")),
            alias: str = "lib/core.py",
            target_state: TargetState = TargetState.OPEN,
        ) -> None:
            self.state.node_states[node] = target_state
            self.state.node_to_alias[node] = alias
            self.state.alias_to_node[alias] = node
        ctx.update(_consequent)

    # ==============================================================================
    # 2. SessionCoordinator Transitions
    # ==============================================================================

    @transition(name="open_targets")
    def open_targets(
        self,
        ctx: TransitionContext[SessionCoordinator, [], Sequence[DagNode]],
    ) -> None:
        ctx.returns(lambda: tuple(n for n, s in self.state.node_states.items() if s == TargetState.OPEN))

    @transition(SessionCoordinator.register_node)
    def register_node(
        self,
        ctx: TransitionContext[SessionCoordinator, [DagNode, str, TargetState], None],
    ) -> None:
        ctx.arguments(
                    node=Domain(strategy=lambda: DagNode(UnitAddress('mod'), RoleAddress('lib'))),
                    alias=Domain(strategy=lambda: 'lib/mod.py'),
                    target_state=Domain(strategy=lambda: TargetState.OPEN),
                )
        def _consequent(
            res: None,
            node: DagNode = DagNode(UnitAddress("mod"), RoleAddress("lib")),
            alias: str = "lib/mod.py",
            target_state: TargetState = TargetState.OPEN,
        ) -> None:
            self.state.node_states[node] = target_state
            self.state.node_to_alias[node] = alias
            self.state.alias_to_node[alias] = node
        ctx.update(_consequent)

    @transition(SessionCoordinator.reset_nodes)
    def reset_nodes(
        self,
        ctx: TransitionContext[SessionCoordinator, [Sequence[DagNode]], None],
    ) -> None:
        ctx.arguments(nodes=Domain(strategy=lambda: ()))
        def _consequent(res: None, nodes: Sequence[DagNode] = ()) -> None:
            self.state.node_states.clear()
            self.state.node_to_alias.clear()
            self.state.alias_to_node.clear()
            for n in nodes:
                alias = f"{n.role_address}/{n.unit_address}.py"
                self.state.node_states[n] = TargetState.OPEN
                self.state.node_to_alias[n] = alias
                self.state.alias_to_node[alias] = n
        ctx.update(_consequent)

    @transition(SessionCoordinator.resolve_default_target)
    def resolve_default_target(
        self,
        ctx: TransitionContext[SessionCoordinator, [Optional[Any]], Optional[DagNode]],
    ) -> None:
        ctx.arguments(last_accessed_file=Domain(strategy=lambda: None))
        def _returns(last_accessed_file: Optional[Any] = None) -> Optional[DagNode]:
            open_nodes = [n for n, s in self.state.node_states.items() if s == TargetState.OPEN]
            return open_nodes[0] if len(open_nodes) == 1 else None
        ctx.returns(_returns)

    @transition(SessionCoordinator.get_node_for_alias)
    def get_node_for_alias(
        self,
        ctx: TransitionContext[SessionCoordinator, [str], Optional[DagNode]],
    ) -> None:
        ctx.arguments(alias=Domain(strategy=lambda: 'lib/core.py'))
        ctx.returns(lambda alias="lib/core.py": self.state.alias_to_node.get(alias))

    @transition(SessionCoordinator.get_alias_for_node)
    def get_alias_for_node(
        self,
        ctx: TransitionContext[SessionCoordinator, [DagNode], str],
    ) -> None:
        ctx.arguments(node=Domain(strategy=lambda: (next(iter(self.state.node_to_alias.keys())),) if self.state.node_to_alias else (DagNode(UnitAddress('u'), RoleAddress('r')),)))
        ctx.returns(lambda node: self.state.node_to_alias.get(node, f"{node.role_address}/{node.unit_address}"))

    @transition(SessionCoordinator.dispatch_get_work)
    def dispatch_get_work(
        self,
        ctx: TransitionContext[SessionCoordinator, [Optional[subgraph.DagSubgraph], Optional[str], Optional[int]], WorkSchedule],
    ) -> None:
        ctx.arguments(
                    subgraph=Domain(strategy=lambda: None),
                    dir_scope=Domain(strategy=lambda: None),
                    max_batch_size=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda subgraph=None, dir_scope=None, max_batch_size=None: WorkSchedule(tasks=tuple(self.state.tasks)))

    @transition(SessionCoordinator.dispatch_check_files)
    def dispatch_check_files(
        self,
        ctx: TransitionContext[SessionCoordinator, [Optional[str]], VerificationResult],
    ) -> None:
        ctx.arguments(target_alias=Domain(strategy=lambda: None))
        ctx.returns(
            lambda target_alias=None: VerificationResult(
                passed=self.state.verification_passed,
                diagnostic_output="All checks passed." if self.state.verification_passed else "Verification failed.",
            )
        )

    @transition(SessionCoordinator.dispatch_submit)
    def dispatch_submit(
        self,
        ctx: TransitionContext[SessionCoordinator, [Optional[str], Optional[str], bool], ControlDispatchOutcome],
    ) -> None:
        ctx.arguments(
                    target_alias=Domain(strategy=lambda: None),
                    change_summary=Domain(strategy=lambda: 'Change'),
                    has_modifications=Domain(strategy=lambda: True),
                )
        def _returns(target_alias: Optional[str] = None, change_summary: Optional[str] = None, has_modifications: bool = True) -> ControlDispatchOutcome:
            node = self.state.alias_to_node.get(target_alias or "")
            if not node:
                open_nodes = [n for n, s in self.state.node_states.items() if s == TargetState.OPEN]
                node = open_nodes[0] if len(open_nodes) == 1 else None

            if node is None:
                return ControlDispatchOutcome(
                    success=False,
                    message="No target node resolved for submission.",
                    remaining_open_targets=tuple(n for n, s in self.state.node_states.items() if s == TargetState.OPEN),
                )
            elif not self.state.verification_passed:
                return ControlDispatchOutcome(
                    success=False,
                    message="Verification checks failed for target.",
                    remaining_open_targets=tuple(n for n, s in self.state.node_states.items() if s == TargetState.OPEN),
                )
            else:
                rem = tuple(n for n, s in self.state.node_states.items() if s == TargetState.OPEN and n != node)
                return ControlDispatchOutcome(
                    success=True,
                    message=f"Submitted target {node} successfully.",
                    remaining_open_targets=rem,
                )
        ctx.returns(_returns)

        def _consequent(res: ControlDispatchOutcome, target_alias: Optional[str] = None, change_summary: Optional[str] = None, has_modifications: bool = True) -> None:
            if res.success:
                node = self.state.alias_to_node.get(target_alias or "")
                if not node:
                    open_nodes = [n for n, s in self.state.node_states.items() if s == TargetState.OPEN]
                    node = open_nodes[0] if len(open_nodes) == 1 else None
                if node:
                    self.state.node_states[node] = TargetState.CLEAN
        ctx.update(_consequent)

    @transition(SessionCoordinator.dispatch_blame)
    def dispatch_blame(
        self,
        ctx: TransitionContext[SessionCoordinator, [Optional[str], Optional[str], str], ControlDispatchOutcome],
    ) -> None:
        ctx.arguments(
                    source_alias=Domain(strategy=lambda: None),
                    blame_target_alias=Domain(strategy=lambda: 'lib/core.py'),
                    explanation=Domain(strategy=lambda: 'Defect found'),
                )
        def _returns(source_alias: Optional[str] = None, blame_target_alias: Optional[str] = None, explanation: str = "Defect found") -> ControlDispatchOutcome:
            if "\n" in explanation.strip():
                return ControlDispatchOutcome(
                    success=False,
                    message="Critique must be a single paragraph without newline characters.",
                    remaining_open_targets=tuple(n for n, s in self.state.node_states.items() if s == TargetState.OPEN),
                )
            return ControlDispatchOutcome(
                success=True,
                message=f"Blame recorded for {blame_target_alias}.",
                remaining_open_targets=(),
            )
        ctx.returns(_returns)

    @transition(SessionCoordinator.dispatch_fail)
    def dispatch_fail(
        self,
        ctx: TransitionContext[SessionCoordinator, [Optional[str], Optional[str]], ControlDispatchOutcome],
    ) -> None:
        ctx.arguments(
                    target_alias=Domain(strategy=lambda: None),
                    reason=Domain(strategy=lambda: 'Unrecoverable error'),
                )
        def _returns(target_alias: Optional[str] = None, reason: Optional[str] = None) -> ControlDispatchOutcome:
            r = "Unrecoverable error" if reason is None else str(reason)
            return ControlDispatchOutcome(
                success=True,
                message=f"Target failure recorded: {r}",
                remaining_open_targets=(),
            )
        ctx.returns(_returns)

        def _consequent(res: ControlDispatchOutcome, target_alias: Optional[str] = None, reason: Optional[str] = None) -> None:
            for n in self.state.node_states:
                self.state.node_states[n] = TargetState.FAILED
        ctx.update(_consequent)


proto = SessionCoordinatorStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_session_coordinator_fake(state: Optional[SessionCoordinatorState] = None) -> SessionCoordinator:
    """Instantiate a synthesized SessionCoordinator fake."""
    sm = SessionCoordinatorStateMachine(state)
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
        self.sm = SessionCoordinatorStateMachine(self.state)
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
        sm = SessionCoordinatorStateMachine(state)
        nodes = [DagNode(UnitAddress(f"unit_{i}"), RoleAddress("lib")) for i in range(count)]
        for i, n in enumerate(nodes):
            sm.seed_session_node(n, f"alias_{i}", TargetState.OPEN)

        fake = sm.as_fake(SessionCoordinator)
        self.assertEqual(len(fake.open_targets), count)

        # Submitting the first node reduces open targets by 1
        outcome = fake.dispatch_submit("alias_0", "Submitted first node")
        self.assertTrue(outcome.success)
        self.assertEqual(len(fake.open_targets), count - 1)
