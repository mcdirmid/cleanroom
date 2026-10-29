"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceChecker."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict, PretenseSet
from update_with_ai.parts.workspace_cli.lib.check import WorkspaceChecker


@dataclass
class CheckState:
    """Canonical model state for WorkspaceChecker."""
    check_files_code: int = 0
    get_work_code: int = 0
    checked_targets: PretenseDict[str, bool] = field(default_factory=PretenseDict)


class WorkspaceCheckStateMachine(StateMachine[CheckState]):
    """Unified Pretense State Machine for WorkspaceChecker."""

    def __init__(
        self,
        state: Optional[CheckState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or CheckState(), singletons=singletons)

    @transition.seeding(name="seed_check_data")
    def seed_check_data(
        self,
        ctx: TransitionContext[Any, [int, int], None],
    ) -> None:
        ctx.arguments(
                    check_files_code=Domain(strategy=lambda: 0),
                    get_work_code=Domain(strategy=lambda: 0),
                )
        ctx.returns(lambda check_files_code=0, get_work_code=0: None)
        ctx.update(lambda res, check_files_code=0, get_work_code=0: (
            setattr(self.state, "check_files_code", int(check_files_code)),
            setattr(self.state, "get_work_code", int(get_work_code)),
        ))

    @transition(WorkspaceChecker.run_get_work)
    def run_get_work(
        self,
        ctx: TransitionContext[WorkspaceChecker, [Optional[str], Optional[str], bool, Optional[int]], int],
    ) -> None:
        ctx.arguments(
                    dir_scope=Domain(strategy=lambda: None),
                    repo_root=Domain(strategy=lambda: None),
                    force=Domain(strategy=lambda: False),
                    batch_size=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda dir_scope=None, repo_root=None, force=False, batch_size=None: self.state.get_work_code)
        ctx.update(lambda res, dir_scope=None, repo_root=None, force=False, batch_size=None: None)

    @transition(WorkspaceChecker.run_check_files)
    def run_check_files(
        self,
        ctx: TransitionContext[WorkspaceChecker, [Optional[str], Optional[str]], int],
    ) -> None:
        ctx.arguments(
                    target=Domain(strategy=lambda: None),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda target=None, repo_root=None: self.state.check_files_code)
        def provide(res: int, target: Optional[str] = None, repo_root: Optional[str] = None) -> None:
            if target:
                self.state.checked_targets[target] = (self.state.check_files_code == 0)
        ctx.update(provide)

    @transition(WorkspaceChecker.is_checked_since_modification)
    def is_checked_since_modification(
        self,
        ctx: TransitionContext[WorkspaceChecker, [str, str], bool],
    ) -> None:
        ctx.arguments(
                    ws_root=Domain(strategy=lambda: '/tmp/ws'),
                    target_path=Domain(strategy=lambda: 'lib/foo.py'),
                )
        ctx.returns(lambda ws_root="/tmp/ws", target_path="lib/foo.py": self.state.checked_targets.get(target_path, False))
        ctx.update(lambda res, ws_root="/tmp/ws", target_path="lib/foo.py": None)

    @transition(WorkspaceChecker.record_check_executed)
    def record_check_executed(
        self,
        ctx: TransitionContext[WorkspaceChecker, [str, str, bool], None],
    ) -> None:
        ctx.arguments(
                    ws_root=Domain(strategy=lambda: '/tmp/ws'),
                    target_path=Domain(strategy=lambda: 'lib/foo.py'),
                    passed=Domain(strategy=lambda: True),
                )
        ctx.returns(lambda ws_root="/tmp/ws", target_path="lib/foo.py", passed=True: None)
        ctx.update(lambda res, ws_root="/tmp/ws", target_path="lib/foo.py", passed=True: (
            self.state.checked_targets.__setitem__(target_path, passed)
        ))


proto = WorkspaceCheckStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_check_fake(state: Optional[CheckState] = None) -> WorkspaceChecker:
    """Instantiate a synthesized WorkspaceChecker fake."""
    st = state or CheckState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspaceChecker)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspaceCheckerUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspaceChecker fake."""

    def setUp(self) -> None:
        self.state = CheckState()
        self.sm = proto.make_state_machine(self.state)
        self.fake: WorkspaceChecker = self.sm.as_fake(WorkspaceChecker)

    def test_run_get_work(self) -> None:
        self.assertEqual(self.fake.run_get_work(), 0)

    def test_run_check_files(self) -> None:
        self.assertEqual(self.fake.run_check_files("lib/foo.py"), 0)
        self.assertTrue(self.fake.is_checked_since_modification("/tmp", "lib/foo.py"))


class TestWorkspaceCheckerImplReal(unittest.TestCase):
    """Direct unit tests for check_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.metadata.lib import src_metadata_impl
        from update_with_ai.parts.workspace.lib import role_registry_impl, roles_impl
        from update_with_ai.parts.workspace_cli.lib import check, check_impl, pending_impl

        self.registry = LifecycleRegistry()
        src_metadata_impl.__initialize__(self.registry)
        roles_impl.__initialize__(self.registry)
        role_registry_impl.__initialize__(self.registry)
        pending_impl.__initialize__(self.registry)
        check_impl.__initialize__(self.registry)

        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.checker = self.scope.get_singleton(check_impl.WorkspaceChecker)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_record_and_is_checked_since_modification(self) -> None:
        with tempfile.TemporaryDirectory() as ws_dir:
            target_f = os.path.join(ws_dir, "sample.py")
            with open(target_f, "w", encoding="utf-8") as f:
                f.write("x = 1\n")

            self.assertFalse(self.checker.is_checked_since_modification(ws_dir, target_f))

            self.checker.record_check_executed(ws_dir, target_f, passed=True)
            self.assertTrue(self.checker.is_checked_since_modification(ws_dir, target_f))

            # Modify file -> invalidates checked status
            with open(target_f, "w", encoding="utf-8") as f:
                f.write("x = 2\n")
            self.assertFalse(self.checker.is_checked_since_modification(ws_dir, target_f))


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspaceCheckerFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspaceChecker."""

    @settings(max_examples=30)
    @given(
        passed=st.booleans(),
        target=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
    )
    def test_checker_invariants(self, passed: bool, target: str) -> None:
        state = CheckState()
        sm = proto.make_state_machine(state)
        fake = sm.as_fake(WorkspaceChecker)

        fake.record_check_executed("/tmp", target, passed=passed)
        self.assertEqual(fake.is_checked_since_modification("/tmp", target), passed)
