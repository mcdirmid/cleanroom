"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspacePendingManager."""

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
from update_with_ai.parts.workspace_cli.lib.pending import WorkspacePendingManager


@dataclass
class PendingState:
    """Canonical model state for WorkspacePendingManager."""
    pending_targets: PretenseSet[str] = field(default_factory=PretenseSet)
    dirty_targets: PretenseSet[str] = field(default_factory=PretenseSet)


class WorkspacePendingStateMachine(StateMachine[PendingState]):
    """Unified Pretense State Machine for WorkspacePendingManager."""

    def __init__(
        self,
        state: Optional[PendingState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or PendingState(), singletons=singletons)

    @transition.seeding(name="seed_pending_data")
    def seed_pending_data(
        self,
        ctx: TransitionContext[Any, [Optional[Sequence[str]], Optional[Sequence[str]]], None],
    ) -> None:
        ctx.arguments(
                    targets=Domain(strategy=lambda: ('part/sample.py',)),
                    dirty_targets=Domain(strategy=lambda: ('part/sample.py',)),
                )
        ctx.returns(lambda targets=None, dirty_targets=None: None)
        ctx.update(lambda res, targets=None, dirty_targets=None: (
            self.state.pending_targets.update(targets or ()),
            self.state.dirty_targets.update(dirty_targets or ()),
        ))

    @transition(WorkspacePendingManager.get_pending_work)
    def get_pending_work(self, ctx: TransitionContext[WorkspacePendingManager, [str], Sequence[str]]) -> None:
        ctx.arguments(workspace_dir=Domain(strategy=lambda: '/tmp/ws'))
        ctx.returns(lambda workspace_dir="/tmp/ws": tuple(sorted(self.state.pending_targets)))
        ctx.update(lambda res, workspace_dir="/tmp/ws": None)

    @transition(WorkspacePendingManager.set_pending_work)
    def set_pending_work(self, ctx: TransitionContext[WorkspacePendingManager, [str, Sequence[str]], None]) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    targets=Domain(strategy=lambda: ('part/foo.py',)),
                )
        ctx.returns(lambda workspace_dir="/tmp/ws", targets=(): None)
        ctx.update(lambda res, workspace_dir="/tmp/ws", targets=(): (
            self.state.pending_targets.clear(),
            self.state.pending_targets.update(targets),
        ))

    @transition(WorkspacePendingManager.remove_pending_target)
    def remove_pending_target(self, ctx: TransitionContext[WorkspacePendingManager, [str, str], None]) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    submitted_target=Domain(strategy=lambda: 'part/foo.py'),
                )
        def _remove(submitted_target: str) -> None:
            self.state.pending_targets.discard(submitted_target)
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
            for t in list(self.state.pending_targets):
                if _norm(t) == sub_stem:
                    self.state.pending_targets.discard(t)
        ctx.returns(lambda workspace_dir="/tmp/ws", submitted_target="part/foo.py": None)
        ctx.update(lambda res, workspace_dir="/tmp/ws", submitted_target="part/foo.py": _remove(submitted_target))

    @transition(WorkspacePendingManager.clear_pending_work)
    def clear_pending_work(self, ctx: TransitionContext[WorkspacePendingManager, [str], None]) -> None:
        ctx.arguments(workspace_dir=Domain(strategy=lambda: '/tmp/ws'))
        ctx.returns(lambda workspace_dir="/tmp/ws": None)
        ctx.update(lambda res, workspace_dir="/tmp/ws": self.state.pending_targets.clear())

    @transition(WorkspacePendingManager.is_pending_target_dirty)
    def is_pending_target_dirty(
        self,
        ctx: TransitionContext[WorkspacePendingManager, [str, str, Optional[str], Optional[str]], bool],
    ) -> None:
        ctx.arguments(
                    target_path=Domain(strategy=lambda: 'part/foo.py'),
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    main_root=Domain(strategy=lambda: None),
                    role_name=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda target_path="part/foo.py", workspace_dir="/tmp/ws", main_root=None, role_name=None: (
            target_path in self.state.dirty_targets
        ))
        ctx.update(lambda res, target_path="part/foo.py", workspace_dir="/tmp/ws", main_root=None, role_name=None: None)


proto = WorkspacePendingStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_pending_fake(state: Optional[PendingState] = None) -> WorkspacePendingManager:
    """Instantiate a synthesized WorkspacePendingManager fake."""
    sm = WorkspacePendingStateMachine(state=state)
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
