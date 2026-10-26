"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceChecker."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.workspace_cli.lib.check import WorkspaceChecker


@dataclass
class CheckState:
    """Canonical model state for WorkspaceChecker."""
    check_files_code: int = 0
    get_work_code: int = 0
    checked_targets: PretenseDict[str, bool] = field(default_factory=PretenseDict)


proto = StateMachineProto[CheckState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_check_data(): pass

@seed_check_data.arguments
def _(
    state: CheckState,
    this: Any,
    check_files_code: int | NotBoundType = NotBound,
    get_work_code: int | NotBoundType = NotBound,
) -> Optional[Tuple[int, int]]:
    c = 0 if isinstance(check_files_code, NotBoundType) else int(check_files_code)
    g = 0 if isinstance(get_work_code, NotBoundType) else int(get_work_code)
    return (c, g)

@seed_check_data.provide
def _(
    state: CheckState,
    this: Any,
    check_files_code: int,
    get_work_code: int,
    result: None = None,
) -> None:
    state.check_files_code = check_files_code
    state.get_work_code = get_work_code


# ==============================================================================
# 2. Check Transitions
# ==============================================================================

@proto.transition(WorkspaceChecker.run_get_work)
def run_get_work(): pass

@run_get_work.arguments
def _(
    state: CheckState,
    this: Any,
    dir_scope: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
    force: bool | NotBoundType = NotBound,
    batch_size: Optional[int] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str], Optional[str], bool, Optional[int]]]:
    ds = None if isinstance(dir_scope, NotBoundType) else dir_scope
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    f = False if isinstance(force, NotBoundType) else bool(force)
    bs = None if isinstance(batch_size, NotBoundType) else batch_size
    return (ds, rr, f, bs)

@run_get_work.returns
def _(
    state: CheckState,
    this: Any,
    dir_scope: Optional[str],
    repo_root: Optional[str],
    force: bool,
    batch_size: Optional[int],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    return Value(state.get_work_code)


@proto.transition(WorkspaceChecker.run_check_files)
def run_check_files(): pass

@run_check_files.arguments
def _(
    state: CheckState,
    this: Any,
    target: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str], Optional[str]]]:
    t = None if isinstance(target, NotBoundType) else target
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    return (t, rr)

@run_check_files.returns
def _(
    state: CheckState,
    this: Any,
    target: Optional[str],
    repo_root: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    if target:
        state.checked_targets[target] = (state.check_files_code == 0)
    return Value(state.check_files_code)


@proto.transition(WorkspaceChecker.is_checked_since_modification)
def is_checked_since_modification(): pass

@is_checked_since_modification.arguments
def _(
    state: CheckState,
    this: Any,
    ws_root: str | NotBoundType = NotBound,
    target_path: str | NotBoundType = NotBound,
) -> Optional[Tuple[str, str]]:
    ws = "/tmp/ws" if isinstance(ws_root, NotBoundType) else str(ws_root)
    tp = "lib/foo.py" if isinstance(target_path, NotBoundType) else str(target_path)
    return (ws, tp)

@is_checked_since_modification.returns
def _(
    state: CheckState,
    this: Any,
    ws_root: str,
    target_path: str,
    outcome: object = NotBound,
) -> Optional[Outcome[bool]]:
    expected = state.checked_targets.get(target_path, False)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(WorkspaceChecker.record_check_executed)
def record_check_executed(): pass

@record_check_executed.arguments
def _(
    state: CheckState,
    this: Any,
    ws_root: str | NotBoundType = NotBound,
    target_path: str | NotBoundType = NotBound,
    passed: bool | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, bool]]:
    ws = "/tmp/ws" if isinstance(ws_root, NotBoundType) else str(ws_root)
    tp = "lib/foo.py" if isinstance(target_path, NotBoundType) else str(target_path)
    p = True if isinstance(passed, NotBoundType) else bool(passed)
    return (ws, tp, p)

@record_check_executed.returns
def _(
    state: CheckState,
    this: Any,
    ws_root: str,
    target_path: str,
    passed: bool,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.checked_targets[target_path] = passed
    return Value(None)


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
