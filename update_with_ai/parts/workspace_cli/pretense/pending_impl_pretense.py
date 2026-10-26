"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspacePendingManager."""

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
from update_with_ai.parts.workspace_cli.lib.pending import WorkspacePendingManager


@dataclass
class PendingState:
    """Canonical model state for WorkspacePendingManager."""
    pending_targets: PretenseSet[str] = field(default_factory=PretenseSet)
    dirty_targets: PretenseSet[str] = field(default_factory=PretenseSet)


proto = StateMachineProto[PendingState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_pending_data(): pass

@seed_pending_data.arguments
def _(
    state: PendingState,
    this: Any,
    targets: Optional[Sequence[str]] | NotBoundType = NotBound,
    dirty_targets: Optional[Sequence[str]] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[str], Sequence[str]]]:
    t = ("part/sample.py",) if isinstance(targets, NotBoundType) or targets is None else tuple(targets)
    d = ("part/sample.py",) if isinstance(dirty_targets, NotBoundType) or dirty_targets is None else tuple(dirty_targets)
    return (t, d)

@seed_pending_data.provide
def _(
    state: PendingState,
    this: Any,
    targets: Sequence[str],
    dirty_targets: Sequence[str],
    result: None = None,
) -> None:
    state.pending_targets.update(targets)
    state.dirty_targets.update(dirty_targets)


# ==============================================================================
# 2. Pending Transitions
# ==============================================================================

@proto.transition(WorkspacePendingManager.get_pending_work)
def get_pending_work(): pass

@get_pending_work.arguments
def _(
    state: PendingState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    return (ws,)

@get_pending_work.returns
def _(
    state: PendingState,
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


@proto.transition(WorkspacePendingManager.set_pending_work)
def set_pending_work(): pass

@set_pending_work.arguments
def _(
    state: PendingState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    targets: Sequence[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, Sequence[str]]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    t = ("part/foo.py",) if isinstance(targets, NotBoundType) else tuple(targets)
    return (ws, t)

@set_pending_work.returns
def _(
    state: PendingState,
    this: Any,
    workspace_dir: str,
    targets: Sequence[str],
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.pending_targets.clear()
    state.pending_targets.update(targets)
    return Value(None)


@proto.transition(WorkspacePendingManager.remove_pending_target)
def remove_pending_target(): pass

@remove_pending_target.arguments
def _(
    state: PendingState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    submitted_target: str | NotBoundType = NotBound,
) -> Optional[Tuple[str, str]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    t = "part/foo.py" if isinstance(submitted_target, NotBoundType) else str(submitted_target)
    return (ws, t)

@remove_pending_target.returns
def _(
    state: PendingState,
    this: Any,
    workspace_dir: str,
    submitted_target: str,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.pending_targets.discard(submitted_target)
    def _norm(s: str) -> str:
        stem = os.path.splitext(os.path.basename(s.replace("\\", "/")))[0]
        changed = True
        while changed:
            changed = False
            for sfx in ("_pretense", "_test", "_impl"):
                if stem.endswith(sfx):
                    stem = stem[: -len(sfx)]
                    changed = True
                    break
        return stem
    sub_stem = _norm(submitted_target)
    for t in list(state.pending_targets):
        if _norm(t) == sub_stem:
            state.pending_targets.discard(t)
    return Value(None)


@proto.transition(WorkspacePendingManager.clear_pending_work)
def clear_pending_work(): pass

@clear_pending_work.arguments
def _(
    state: PendingState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    return (ws,)

@clear_pending_work.returns
def _(
    state: PendingState,
    this: Any,
    workspace_dir: str,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.pending_targets.clear()
    return Value(None)


@proto.transition(WorkspacePendingManager.is_pending_target_dirty)
def is_pending_target_dirty(): pass

@is_pending_target_dirty.arguments
def _(
    state: PendingState,
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
    state: PendingState,
    this: Any,
    target_path: str,
    workspace_dir: str,
    main_root: Optional[str],
    role_name: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[bool]]:
    expected = target_path in state.dirty_targets
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_pending_fake(state: Optional[PendingState] = None) -> WorkspacePendingManager:
    """Instantiate a synthesized WorkspacePendingManager fake."""
    st = state or PendingState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspacePendingManager)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspacePendingUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspacePendingManager fake."""

    def setUp(self) -> None:
        self.state = PendingState()
        self.sm = proto.make_state_machine(self.state)
        self.sm.seed_pending_data(
            targets=["a.py", "b.py"],
            dirty_targets=["a.py"],
        )
        self.fake: WorkspacePendingManager = self.sm.as_fake(WorkspacePendingManager)

    def test_get_and_set_pending(self) -> None:
        self.assertEqual(sorted(self.fake.get_pending_work("/tmp")), ["a.py", "b.py"])
        self.fake.set_pending_work("/tmp", ["c.py"])
        self.assertEqual(list(self.fake.get_pending_work("/tmp")), ["c.py"])

    def test_remove_and_clear(self) -> None:
        self.fake.remove_pending_target("/tmp", "a.py")
        self.assertEqual(list(self.fake.get_pending_work("/tmp")), ["b.py"])
        self.fake.clear_pending_work("/tmp")
        self.assertEqual(list(self.fake.get_pending_work("/tmp")), [])

    def test_is_pending_target_dirty(self) -> None:
        self.assertTrue(self.fake.is_pending_target_dirty("a.py", "/tmp"))
        self.assertFalse(self.fake.is_pending_target_dirty("b.py", "/tmp"))


class TestWorkspacePendingImplReal(unittest.TestCase):
    """Direct unit tests for pending_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.metadata.lib import src_metadata_impl
        from update_with_ai.parts.workspace_cli.lib import pending, pending_impl

        self.registry = LifecycleRegistry()
        src_metadata_impl.__initialize__(self.registry)
        pending_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.pending_mgr = self.scope.get_singleton(pending_impl.WorkspacePendingManager)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_get_set_remove_clear(self) -> None:
        with tempfile.TemporaryDirectory() as ws_dir:
            self.assertEqual(self.pending_mgr.get_pending_work(ws_dir), ())

            targets = ["part/a.py", "part/b.py"]
            self.pending_mgr.set_pending_work(ws_dir, targets)
            self.assertEqual(list(self.pending_mgr.get_pending_work(ws_dir)), targets)

            self.pending_mgr.remove_pending_target(ws_dir, "part/a.py")
            self.assertEqual(list(self.pending_mgr.get_pending_work(ws_dir)), ["part/b.py"])

            self.pending_mgr.clear_pending_work(ws_dir)
            self.assertEqual(self.pending_mgr.get_pending_work(ws_dir), ())

    def test_is_pending_target_dirty(self) -> None:
        from update_with_ai.parts.metadata.lib import src_metadata

        with tempfile.TemporaryDirectory() as ws_dir:
            # Missing file is dirty
            self.assertTrue(self.pending_mgr.is_pending_target_dirty("missing.py", ws_dir))

            target = os.path.join(ws_dir, "test.py")
            with open(target, "w", encoding="utf-8") as f:
                f.write("x = 1\n")

            # Dirty flag
            src_metadata.update_metadata(target, dirty="Fix error")
            self.assertTrue(self.pending_mgr.is_pending_target_dirty("test.py", ws_dir))

            # Clean
            src_metadata.update_metadata(
                target,
                last_cleaned="2026-10-10T12:00:00Z",
                last_changed="2026-10-10T12:00:00Z",
                clear_dirty=True,
            )
            self.assertFalse(self.pending_mgr.is_pending_target_dirty("test.py", ws_dir))


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspacePendingFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspacePendingManager."""

    @settings(max_examples=30)
    @given(
        targets=st.lists(
            st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    def test_pending_invariants(self, targets: list[str]) -> None:
        state = PendingState()
        sm = proto.make_state_machine(state)
        fake = sm.as_fake(WorkspacePendingManager)

        fake.set_pending_work("/tmp", targets)
        self.assertEqual(set(fake.get_pending_work("/tmp")), set(targets))

        fake.clear_pending_work("/tmp")
        self.assertEqual(len(fake.get_pending_work("/tmp")), 0)
