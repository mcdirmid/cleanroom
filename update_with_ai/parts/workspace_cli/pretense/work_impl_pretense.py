"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceWorkManager."""

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
from update_with_ai.parts.workspace_cli.lib.work import (
    WorkQueueItem,
    WorkQueueSummary,
    WorkspaceWorkManager,
)


@dataclass
class WorkState:
    """Canonical model state for WorkspaceWorkManager."""
    pending_targets: PretenseSet[str] = field(default_factory=PretenseSet)
    ready_targets: PretenseSet[str] = field(default_factory=PretenseSet)
    blocked_targets: PretenseSet[str] = field(default_factory=PretenseSet)


proto = StateMachineProto[WorkState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_work_data(): pass

@seed_work_data.arguments
def _(
    state: WorkState,
    this: Any,
    ready_targets: Optional[Sequence[str]] | NotBoundType = NotBound,
    blocked_targets: Optional[Sequence[str]] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[str], Sequence[str]]]:
    r = ("part/sample.py",) if isinstance(ready_targets, NotBoundType) or ready_targets is None else tuple(ready_targets)
    b = () if isinstance(blocked_targets, NotBoundType) or blocked_targets is None else tuple(blocked_targets)
    return (r, b)

@seed_work_data.provide
def _(
    state: WorkState,
    this: Any,
    ready_targets: Sequence[str],
    blocked_targets: Sequence[str],
    result: None = None,
) -> None:
    state.ready_targets.update(ready_targets)
    state.blocked_targets.update(blocked_targets)


# ==============================================================================
# 2. Work Transitions
# ==============================================================================

@proto.transition(WorkspaceWorkManager.get_pending_work)
def get_pending_work(): pass

@get_pending_work.arguments
def _(
    state: WorkState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    return (ws,)

@get_pending_work.returns
def _(
    state: WorkState,
    this: Any,
    workspace_dir: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Sequence[str]]]:
    expected = tuple(sorted(state.pending_targets))
    if isinstance(outcome, Value) and tuple(outcome.val) == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(WorkspaceWorkManager.set_pending_work)
def set_pending_work(): pass

@set_pending_work.arguments
def _(
    state: WorkState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    targets: Sequence[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, Sequence[str]]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    t = ("part/foo.py",) if isinstance(targets, NotBoundType) else tuple(targets)
    return (ws, t)

@set_pending_work.returns
def _(
    state: WorkState,
    this: Any,
    workspace_dir: str,
    targets: Sequence[str],
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.pending_targets.clear()
    state.pending_targets.update(targets)
    return Value(None)


@proto.transition(WorkspaceWorkManager.clear_pending_work)
def clear_pending_work(): pass

@clear_pending_work.arguments
def _(
    state: WorkState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    return (ws,)

@clear_pending_work.returns
def _(
    state: WorkState,
    this: Any,
    workspace_dir: str,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.pending_targets.clear()
    return Value(None)


@proto.transition(WorkspaceWorkManager.remove_pending_target)
def remove_pending_target(): pass

@remove_pending_target.arguments
def _(
    state: WorkState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    submitted_target: str | NotBoundType = NotBound,
) -> Optional[Tuple[str, str]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    t = "part/foo.py" if isinstance(submitted_target, NotBoundType) else str(submitted_target)
    return (ws, t)

@remove_pending_target.returns
def _(
    state: WorkState,
    this: Any,
    workspace_dir: str,
    submitted_target: str,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.pending_targets.discard(submitted_target)
    return Value(None)


@proto.transition(WorkspaceWorkManager.is_pending_target_dirty)
def is_pending_target_dirty(): pass

@is_pending_target_dirty.arguments
def _(
    state: WorkState,
    this: Any,
    target_path: str | NotBoundType = NotBound,
    workspace_dir: str | NotBoundType = NotBound,
    main_root: Optional[str] | NotBoundType = NotBound,
    role_name: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, Optional[str], Optional[str]]]:
    t = "part/foo.py" if isinstance(target_path, NotBoundType) else str(target_path)
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    mr = None if isinstance(main_root, NotBoundType) else main_root
    rn = None if isinstance(role_name, NotBoundType) else role_name
    return (t, ws, mr, rn)

@is_pending_target_dirty.returns
def _(
    state: WorkState,
    this: Any,
    target_path: str,
    workspace_dir: str,
    main_root: Optional[str],
    role_name: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[bool]]:
    expected = target_path in state.ready_targets or target_path in state.blocked_targets
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(WorkspaceWorkManager.compute_role_work_queue)
def compute_role_work_queue(): pass

@compute_role_work_queue.arguments
def _(
    state: WorkState,
    this: Any,
    role_name: str | NotBoundType = NotBound,
    dir_scope: str | NotBoundType = NotBound,
    repo_root: str | NotBoundType = NotBound,
    target_unit: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, str, Optional[str]]]:
    rn = "lib" if isinstance(role_name, NotBoundType) else str(role_name)
    ds = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    rr = "/tmp/repo" if isinstance(repo_root, NotBoundType) else str(repo_root)
    tu = None if isinstance(target_unit, NotBoundType) else target_unit
    return (rn, ds, rr, tu)

@compute_role_work_queue.returns
def _(
    state: WorkState,
    this: Any,
    role_name: str,
    dir_scope: str,
    repo_root: str,
    target_unit: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[Tuple[Sequence[WorkQueueItem], Sequence[WorkQueueItem]]]]:
    ready = [
        WorkQueueItem(
            target_file=t,
            role_name=role_name,
            dirtiness_reasons=("dirty",),
            dependency_files=(),
            is_ready=True,
        )
        for t in sorted(state.ready_targets)
    ]
    blocked = [
        WorkQueueItem(
            target_file=t,
            role_name=role_name,
            dirtiness_reasons=("blocked on dep",),
            dependency_files=(),
            is_ready=False,
            blocked_reasons=("upstream dirty",),
        )
        for t in sorted(state.blocked_targets)
    ]
    return Value((ready, blocked))


@proto.transition(WorkspaceWorkManager.evaluate_work)
def evaluate_work(): pass

@evaluate_work.arguments
def _(
    state: WorkState,
    this: Any,
    dir_scope: str | NotBoundType = NotBound,
    role_name: str | NotBoundType = NotBound,
    workspace_dir: Optional[str] | NotBoundType = NotBound,
    force: bool | NotBoundType = NotBound,
    batch_size: Optional[int] | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, Optional[str], bool, Optional[int]]]:
    ds = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    rn = "lib" if isinstance(role_name, NotBoundType) else str(role_name)
    ws = None if isinstance(workspace_dir, NotBoundType) else workspace_dir
    f = False if isinstance(force, NotBoundType) else bool(force)
    bs = None if isinstance(batch_size, NotBoundType) else batch_size
    return (ds, rn, ws, f, bs)

@evaluate_work.returns
def _(
    state: WorkState,
    this: Any,
    dir_scope: str,
    role_name: str,
    workspace_dir: Optional[str],
    force: bool,
    batch_size: Optional[int],
    outcome: object = NotBound,
) -> Optional[Outcome[WorkQueueSummary]]:
    ready = [
        WorkQueueItem(
            target_file=t,
            role_name=role_name,
            dirtiness_reasons=("dirty",),
            dependency_files=(),
            is_ready=True,
        )
        for t in sorted(state.ready_targets)
    ]
    blocked = [
        WorkQueueItem(
            target_file=t,
            role_name=role_name,
            dirtiness_reasons=("blocked on dep",),
            dependency_files=(),
            is_ready=False,
            blocked_reasons=("upstream dirty",),
        )
        for t in sorted(state.blocked_targets)
    ]
    summary = WorkQueueSummary(
        ready_items=ready,
        blocked_items=blocked,
        is_clean=len(ready) == 0 and len(blocked) == 0,
    )
    return Value(summary)


@proto.transition(WorkspaceWorkManager.resolve_contract_files)
def resolve_contract_files(): pass

@resolve_contract_files.arguments
def _(
    state: WorkState,
    this: Any,
    target_path: str | NotBoundType = NotBound,
    workspace_dir: str | NotBoundType = NotBound,
    role_name: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, Optional[str]]]:
    tp = "part/sample.py" if isinstance(target_path, NotBoundType) else str(target_path)
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    rn = None if isinstance(role_name, NotBoundType) else role_name
    return (tp, ws, rn)

@resolve_contract_files.returns
def _(
    state: WorkState,
    this: Any,
    target_path: str,
    workspace_dir: str,
    role_name: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[Sequence[str]]]:
    return Value(())


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_work_fake(state: Optional[WorkState] = None) -> WorkspaceWorkManager:
    """Instantiate a synthesized WorkspaceWorkManager fake."""
    st = state or WorkState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspaceWorkManager)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspaceWorkUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspaceWorkManager fake."""

    def setUp(self) -> None:
        self.state = WorkState()
        self.sm = proto.make_state_machine(self.state)
        self.sm.seed_work_data(
            ready_targets=["lib/foo.py"],
            blocked_targets=["lib/bar.py"],
        )
        self.fake: WorkspaceWorkManager = self.sm.as_fake(WorkspaceWorkManager)

    def test_evaluate_work(self) -> None:
        summary = self.fake.evaluate_work("staging", "lib")
        self.assertEqual(len(summary.ready_items), 1)
        self.assertEqual(len(summary.blocked_items), 1)
        self.assertFalse(summary.is_clean)

    def test_compute_role_work_queue(self) -> None:
        ready, blocked = self.fake.compute_role_work_queue("lib", "staging", "/repo")
        self.assertEqual(len(ready), 1)
        self.assertEqual(len(blocked), 1)


class TestWorkspaceWorkImplReal(unittest.TestCase):
    """Direct unit tests for work_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.metadata.lib import src_metadata_impl
        from update_with_ai.parts.workspace.lib import role_registry_impl, roles_impl
        from update_with_ai.parts.workspace_cli.lib import dirtiness_impl, pending_impl, work, work_impl

        self.registry = LifecycleRegistry()
        src_metadata_impl.__initialize__(self.registry)
        roles_impl.__initialize__(self.registry)
        role_registry_impl.__initialize__(self.registry)
        pending_impl.__initialize__(self.registry)
        dirtiness_impl.__initialize__(self.registry)
        work_impl.__initialize__(self.registry)

        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.work_mgr = self.scope.get_singleton(work_impl.WorkspaceWorkManager)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_pending_delegates(self) -> None:
        with tempfile.TemporaryDirectory() as ws_dir:
            self.assertEqual(self.work_mgr.get_pending_work(ws_dir), ())
            self.work_mgr.set_pending_work(ws_dir, ["lib/foo.py"])
            self.assertEqual(list(self.work_mgr.get_pending_work(ws_dir)), ["lib/foo.py"])
            self.work_mgr.remove_pending_target(ws_dir, "lib/foo.py")
            self.assertEqual(self.work_mgr.get_pending_work(ws_dir), ())

    def test_evaluate_work_empty_scope(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            roles_file = os.path.join(repo_root, "cleanroom_roles.toml")
            with open(roles_file, "w", encoding="utf-8") as f:
                f.write('[roles.lib]\nname = "lib"\nsrc_pattern = "{unit_dir}/lib/{unit_name}.py"\n')

            summary = self.work_mgr.evaluate_work(
                dir_scope="empty_scope",
                role_name="lib",
                workspace_dir=repo_root,
            )
            self.assertTrue(summary.is_clean)
            self.assertEqual(len(summary.ready_items), 0)


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspaceWorkFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspaceWorkManager."""

    @settings(max_examples=30)
    @given(
        ready=st.lists(st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"), min_size=0, max_size=4, unique=True),
        blocked=st.lists(st.text(min_size=1, max_size=10, alphabet="1234567890"), min_size=0, max_size=4, unique=True),
    )
    def test_work_invariants(self, ready: list[str], blocked: list[str]) -> None:
        state = WorkState()
        sm = proto.make_state_machine(state)
        sm.seed_work_data(ready_targets=ready, blocked_targets=blocked)
        fake = sm.as_fake(WorkspaceWorkManager)

        summary = fake.evaluate_work("scope", "lib")
        self.assertEqual(len(summary.ready_items), len(ready))
        self.assertEqual(len(summary.blocked_items), len(blocked))
        self.assertEqual(summary.is_clean, len(ready) == 0 and len(blocked) == 0)
