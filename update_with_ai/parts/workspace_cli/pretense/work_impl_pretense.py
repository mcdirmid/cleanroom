"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceWorkManager."""

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


class WorkspaceWorkStateMachine(StateMachine[WorkState]):
    """Unified Pretense State Machine for WorkspaceWorkManager."""

    def __init__(
        self,
        state: Optional[WorkState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or WorkState(), singletons=singletons)

    @transition.seeding(name="seed_work_data")
    def seed_work_data(
        self,
        ctx: TransitionContext[Any, [Optional[Sequence[str]], Optional[Sequence[str]]], None],
    ) -> None:
        ctx.arguments(
                    ready_targets=Domain(strategy=lambda: ('part/sample.py',)),
                    blocked_targets=Domain(strategy=lambda: ()),
                )
        ctx.returns(lambda ready_targets=None, blocked_targets=None: None)
        ctx.update(lambda res, ready_targets=None, blocked_targets=None: (
            self.state.ready_targets.update(ready_targets or ()),
            self.state.blocked_targets.update(blocked_targets or ()),
        ))

    @transition(WorkspaceWorkManager.get_pending_work)
    def get_pending_work(self, ctx: TransitionContext[WorkspaceWorkManager, [str], Sequence[str]]) -> None:
        ctx.arguments(workspace_dir=Domain(strategy=lambda: '/tmp/ws'))
        ctx.returns(lambda workspace_dir="/tmp/ws": tuple(sorted(self.state.pending_targets)))
        ctx.update(lambda res, workspace_dir="/tmp/ws": None)

    @transition(WorkspaceWorkManager.set_pending_work)
    def set_pending_work(self, ctx: TransitionContext[WorkspaceWorkManager, [str, Sequence[str]], None]) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    targets=Domain(strategy=lambda: ('part/foo.py',)),
                )
        ctx.returns(lambda workspace_dir="/tmp/ws", targets=(): None)
        ctx.update(lambda res, workspace_dir="/tmp/ws", targets=(): (
            self.state.pending_targets.clear(),
            self.state.pending_targets.update(targets),
        ))

    @transition(WorkspaceWorkManager.clear_pending_work)
    def clear_pending_work(self, ctx: TransitionContext[WorkspaceWorkManager, [str], None]) -> None:
        ctx.arguments(workspace_dir=Domain(strategy=lambda: '/tmp/ws'))
        ctx.returns(lambda workspace_dir="/tmp/ws": None)
        ctx.update(lambda res, workspace_dir="/tmp/ws": self.state.pending_targets.clear())

    @transition(WorkspaceWorkManager.remove_pending_target)
    def remove_pending_target(self, ctx: TransitionContext[WorkspaceWorkManager, [str, str], None]) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    submitted_target=Domain(strategy=lambda: 'part/foo.py'),
                )
        ctx.returns(lambda workspace_dir="/tmp/ws", submitted_target="part/foo.py": None)
        ctx.update(lambda res, workspace_dir="/tmp/ws", submitted_target="part/foo.py": self.state.pending_targets.discard(submitted_target))

    @transition(WorkspaceWorkManager.is_pending_target_dirty)
    def is_pending_target_dirty(
        self,
        ctx: TransitionContext[WorkspaceWorkManager, [str, str, Optional[str], Optional[str]], bool],
    ) -> None:
        ctx.arguments(
                    target_path=Domain(strategy=lambda: 'part/foo.py'),
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    main_root=Domain(strategy=lambda: None),
                    role_name=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda target_path="part/foo.py", workspace_dir="/tmp/ws", main_root=None, role_name=None: (
            target_path in self.state.ready_targets or target_path in self.state.blocked_targets
        ))
        ctx.update(lambda res, target_path="part/foo.py", workspace_dir="/tmp/ws", main_root=None, role_name=None: None)

    @transition(WorkspaceWorkManager.compute_role_work_queue)
    def compute_role_work_queue(
        self,
        ctx: TransitionContext[WorkspaceWorkManager, [str, str, str, Optional[str]], Tuple[Sequence[WorkQueueItem], Sequence[WorkQueueItem]]],
    ) -> None:
        ctx.arguments(
                    role_name=Domain(strategy=lambda: 'lib'),
                    dir_scope=Domain(strategy=lambda: 'staging'),
                    repo_root=Domain(strategy=lambda: '/tmp/repo'),
                    target_unit=Domain(strategy=lambda: None),
                )
        def _compute_queue(role_name: str, dir_scope: str, repo_root: str, target_unit: Optional[str]) -> Tuple[Sequence[WorkQueueItem], Sequence[WorkQueueItem]]:
            ready = [
                WorkQueueItem(
                    target_file=t,
                    role_name=role_name,
                    dirtiness_reasons=("dirty",),
                    dependency_files=(),
                    is_ready=True,
                )
                for t in sorted(self.state.ready_targets)
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
                for t in sorted(self.state.blocked_targets)
            ]
            return (ready, blocked)
        ctx.returns(lambda role_name="lib", dir_scope="staging", repo_root="/tmp/repo", target_unit=None: _compute_queue(role_name, dir_scope, repo_root, target_unit))
        ctx.update(lambda res, role_name="lib", dir_scope="staging", repo_root="/tmp/repo", target_unit=None: None)

    @transition(WorkspaceWorkManager.evaluate_work)
    def evaluate_work(
        self,
        ctx: TransitionContext[WorkspaceWorkManager, [str, str, Optional[str], bool, Optional[int]], WorkQueueSummary],
    ) -> None:
        ctx.arguments(
                    dir_scope=Domain(strategy=lambda: 'staging'),
                    role_name=Domain(strategy=lambda: 'lib'),
                    workspace_dir=Domain(strategy=lambda: None),
                    force=Domain(strategy=lambda: False),
                    batch_size=Domain(strategy=lambda: None),
                )
        def _eval(dir_scope: str, role_name: str, workspace_dir: Optional[str], force: bool, batch_size: Optional[int]) -> WorkQueueSummary:
            ready = [
                WorkQueueItem(
                    target_file=t,
                    role_name=role_name,
                    dirtiness_reasons=("dirty",),
                    dependency_files=(),
                    is_ready=True,
                )
                for t in sorted(self.state.ready_targets)
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
                for t in sorted(self.state.blocked_targets)
            ]
            return WorkQueueSummary(
                ready_items=ready,
                blocked_items=blocked,
                is_clean=len(ready) == 0 and len(blocked) == 0,
            )
        ctx.returns(lambda dir_scope="staging", role_name="lib", workspace_dir=None, force=False, batch_size=None: _eval(dir_scope, role_name, workspace_dir, force, batch_size))
        ctx.update(lambda res, dir_scope="staging", role_name="lib", workspace_dir=None, force=False, batch_size=None: None)

    @transition(WorkspaceWorkManager.resolve_contract_files)
    def resolve_contract_files(
        self,
        ctx: TransitionContext[WorkspaceWorkManager, [str, str, Optional[str]], Sequence[str]],
    ) -> None:
        ctx.arguments(
                    target_path=Domain(strategy=lambda: 'part/sample.py'),
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    role_name=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda target_path="part/sample.py", workspace_dir="/tmp/ws", role_name=None: ())
        ctx.update(lambda res, target_path="part/sample.py", workspace_dir="/tmp/ws", role_name=None: None)


proto = WorkspaceWorkStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_work_fake(state: Optional[WorkState] = None) -> WorkspaceWorkManager:
    """Instantiate a synthesized WorkspaceWorkManager fake."""
    sm = WorkspaceWorkStateMachine(state=state)
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
