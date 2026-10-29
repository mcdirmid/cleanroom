"""Pretense state machine, fake synthesis, unit tests, and fuzzing for DshHarnessAdapter and DshHarnessManager."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from update_with_ai.parts.dsh.lib import dsh_harness, dsh_telemetry
from update_with_ai.parts.dsh.lib.dsh_harness import DshHarnessAdapter, DshHarnessManager
from update_with_ai.parts.subagent.lib import subagent_coordinator
from update_with_ai.parts.subagent.lib.subagent_coordinator import (
    RoleDispatch,
    RoleRoundResult,
)


@dataclass
class DshHarnessState:
    """Canonical model state for DshHarnessAdapter."""
    active_dispatches: Dict[str, RoleDispatch] = field(default_factory=dict)
    completed_handles: Dict[str, RoleRoundResult] = field(default_factory=dict)
    interrupted_handles: List[str] = field(default_factory=list)


class DshHarnessStateMachine(StateMachine[DshHarnessState]):
    """Unified Pretense State Machine for DshHarnessAdapter."""

    def __init__(
        self,
        state: Optional[DshHarnessState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or DshHarnessState(), singletons=singletons)

    @transition(DshHarnessAdapter.dispatch_role)
    def dispatch_role(
        self,
        ctx: TransitionContext[DshHarnessAdapter, [RoleDispatch], str],
    ) -> None:
        ctx.arguments(dispatch=Domain(strategy=lambda: RoleDispatch(role_name='lib', workspace_dir='/tmp/ws/lib', ready_targets=['//parts/core:core#lib'], dir_scope='staging', batch_size=1)))
        def returns(dispatch: Optional[RoleDispatch] = None) -> str:
            d = dispatch or RoleDispatch(
                role_name="lib",
                workspace_dir="/tmp/ws/lib",
                ready_targets=["//parts/core:core#lib"],
                dir_scope="staging",
                batch_size=1,
            )
            handle = f"dsh-task-{d.role_name}-{len(self.state.active_dispatches) + 1}"
            self.state.active_dispatches[handle] = d
            return handle
        ctx.returns(returns)
        ctx.update(lambda res, dispatch=None: None)

    @transition(DshHarnessAdapter.poll_role)
    def poll_role(
        self,
        ctx: TransitionContext[DshHarnessAdapter, [str], Optional[RoleRoundResult]],
    ) -> None:
        ctx.arguments(task_handle=Domain(strategy=lambda: 'dsh-task-1'))
        def returns(task_handle: str = "dsh-task-1") -> Optional[RoleRoundResult]:
            if task_handle in self.state.completed_handles:
                return self.state.completed_handles[task_handle]
            elif task_handle in self.state.active_dispatches:
                return None
            return RoleRoundResult(
                role="lib",
                status="completed",
                submitted_targets=(),
                blamed_targets=(),
                failure_reason=None,
            )
        ctx.returns(returns)
        ctx.update(lambda res, task_handle="dsh-task-1": None)

    @transition(DshHarnessAdapter.await_role)
    def await_role(
        self,
        ctx: TransitionContext[DshHarnessAdapter, [str], RoleRoundResult],
    ) -> None:
        ctx.arguments(task_handle=Domain(strategy=lambda: 'dsh-task-1'))
        def returns(task_handle: str = "dsh-task-1") -> RoleRoundResult:
            disp = self.state.active_dispatches.get(
                task_handle,
                RoleDispatch(role_name="lib", workspace_dir="/tmp", ready_targets=[], dir_scope=""),
            )
            result = self.state.completed_handles.get(
                task_handle,
                RoleRoundResult(
                    role=disp.role_name,
                    status="completed",
                    submitted_targets=tuple(disp.ready_targets),
                    blamed_targets=(),
                    failure_reason=None,
                ),
            )
            self.state.completed_handles[task_handle] = result
            return result
        ctx.returns(returns)
        ctx.update(lambda res, task_handle="dsh-task-1": None)

    @transition(DshHarnessAdapter.interrupt_role)
    def interrupt_role(
        self,
        ctx: TransitionContext[DshHarnessAdapter, [str], None],
    ) -> None:
        ctx.arguments(task_handle=Domain(strategy=lambda: 'dsh-task-1'))
        ctx.returns(lambda task_handle="dsh-task-1": None)
        ctx.update(lambda res, task_handle="dsh-task-1": self.state.interrupted_handles.append(task_handle))


proto = DshHarnessStateMachine()


# ==============================================================================
# 2. Synthesized Fake Factory
# ==============================================================================

def make_dsh_harness_fake(
    state: Optional[DshHarnessState] = None,
) -> DshHarnessAdapter:
    """Instantiate a synthesized DshHarnessAdapter fake."""
    st = state or DshHarnessState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(DshHarnessAdapter)


# ==============================================================================
# 3. Deterministic Unit Tests
# ==============================================================================

class TestDshHarnessUnit(unittest.TestCase):
    """Deterministic unit tests validating state machine and synthesized fake."""

    def test_dispatch_and_await_round(self) -> None:
        fake = make_dsh_harness_fake()
        disp = RoleDispatch(
            role_name="low",
            workspace_dir="/tmp/ws/low",
            ready_targets=["//parts/core:core#low"],
            dir_scope="staging",
            batch_size=1,
        )
        handle = fake.dispatch_role(disp)
        self.assertTrue(handle.startswith("dsh-task-low"))

        # Poll while active
        polled = fake.poll_role(handle)
        self.assertIsNone(polled)

        # Await completion
        res = fake.await_role(handle)
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.submitted_targets, ("//parts/core:core#low",))

        # Poll after completion
        polled_done = fake.poll_role(handle)
        self.assertIsNotNone(polled_done)
        assert polled_done is not None
        self.assertEqual(polled_done.status, "completed")

    def test_interrupt_role(self) -> None:
        state = DshHarnessState()
        fake = make_dsh_harness_fake(state)
        disp = RoleDispatch(
            role_name="lib",
            workspace_dir="/tmp/ws/lib",
            ready_targets=["//parts/core:core#lib"],
            dir_scope="staging",
            batch_size=1,
        )
        handle = fake.dispatch_role(disp)
        fake.interrupt_role(handle)
        self.assertIn(handle, state.interrupted_handles)


# ==============================================================================
# 4. Hypothesis Fuzz Tests
# ==============================================================================

class TestDshHarnessFuzz(unittest.TestCase):
    """Hypothesis fuzz tests for harness lifecycle invariants."""

    @given(
        role_name=st.sampled_from(["high", "planning", "low", "lib", "test", "qa", "coverage"]),
        targets=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
    )
    @settings(max_examples=25)
    def test_dispatch_lifecycle_invariants(
        self, role_name: str, targets: List[str]
    ) -> None:
        state = DshHarnessState()
        fake = make_dsh_harness_fake(state)
        disp = RoleDispatch(
            role_name=role_name,
            workspace_dir=f"/tmp/ws/{role_name}",
            ready_targets=targets,
            dir_scope="staging",
            batch_size=len(targets),
        )
        handle = fake.dispatch_role(disp)
        self.assertIn(handle, state.active_dispatches)
        self.assertIsNone(fake.poll_role(handle))

        res = fake.await_role(handle)
        self.assertEqual(res.status, "completed")
        self.assertEqual(list(res.submitted_targets), targets)
        self.assertIsNotNone(fake.poll_role(handle))


class FakeWorkspaceRegistry:
    tier = "agent_session"
    def resolve_role_definition(self, role_name_or_address: str, repo_root: Optional[str] = None, dir_scope: Optional[str] = None) -> Any:
        from update_with_ai.parts.workspace.lib.role_registry import RoleDefinition
        clean = role_name_or_address.split(":")[-1].strip().lower()
        return RoleDefinition(
            role_name=clean,
            guide_path=f"guides/{clean}.md",
            writable_file_patterns=[f"{clean}/*"],
            readonly_file_patterns=[],
            feedback_role_deps=[],
        )


class FakeWorkspaceWorkManager:
    tier = "agent_session"
    def __init__(self) -> None:
        self.pending: dict[str, list[str]] = {}
    def get_pending_work(self, workspace_dir: str) -> list[str]:
        return list(self.pending.get(workspace_dir, []))
    def set_pending_work(self, workspace_dir: str, targets: Sequence[str]) -> None:
        self.pending[workspace_dir] = list(targets)
    def clear_pending_work(self, workspace_dir: str) -> None:
        self.pending.pop(workspace_dir, None)
    def remove_pending_target(self, workspace_dir: str, target: str) -> bool:
        items = self.pending.get(workspace_dir, [])
        if target in items:
            items.remove(target)
            return True
        return False


class FakeDshTelemetryParser:
    tier = "agent_session"
    def __init__(self) -> None:
        self.round_status = dsh_telemetry.DshRpcRoundStatus(
            is_active=False,
            is_completed=True,
            metrics=dsh_telemetry.DshSessionTokenMetrics(),
        )
    def is_desktop_server_available(self, sessions_dir: Optional[str] = None) -> bool:
        return True
    def dispatch_round_rpc(self, **kwargs: Any) -> Optional[str]:
        return "dsh_rpc::sid::msg"
    def poll_round_rpc(self, *args: Any, **kwargs: Any) -> dsh_telemetry.DshRpcRoundStatus:
        return self.round_status
    def parse_session_storage(self, *args: Any, **kwargs: Any) -> dsh_telemetry.DshSessionTokenMetrics:
        return dsh_telemetry.DshSessionTokenMetrics()
    def parse_stream_text(self, *args: Any, **kwargs: Any) -> dsh_telemetry.DshSessionTokenMetrics:
        return dsh_telemetry.DshSessionTokenMetrics()


class TestDshHarnessImplReal(unittest.TestCase):
    """Direct tests for dsh_harness_impl.py."""

    def setUp(self) -> None:
        import shutil
        import tempfile
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.dsh.lib import dsh_harness_impl
        from update_with_ai.parts.workspace_cli.lib import work
        from update_with_ai.parts.workspace.lib import role_registry

        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        dsh_harness_impl.__initialize__(self.registry)
        self.work_mgr = FakeWorkspaceWorkManager()
        self.telemetry = FakeDshTelemetryParser()
        self.reg_fake = FakeWorkspaceRegistry()

        self.registry.register_instance(self.reg_fake, keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        self.registry.register_instance(self.work_mgr, keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)
        self.registry.register_instance(self.telemetry, keys=[dsh_telemetry.DshTelemetryParser], tier=agent_session.agent_session)

        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()

    def tearDown(self) -> None:
        import shutil
        self.phase_cm.__exit__(None, None, None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_simulation_round(self) -> None:
        from update_with_ai.parts.dsh.lib.dsh_harness_impl import DshHarnessAdapter
        adapter = DshHarnessAdapter(
            model_name="DeepSeek-V41-Flash",
            simulation_mode=True,
        )
        self.work_mgr.set_pending_work(self.test_dir, ["high/unit_a.md"])
        dispatch = RoleDispatch(
            role_name="high",
            workspace_dir=self.test_dir,
            dir_scope="//pkg",
            ready_targets=("high/unit_a.md",),
            batch_size=1,
            task_prompt="",
        )
        handle = adapter.dispatch_role(dispatch)
        self.assertTrue(handle.startswith("dsh_high_"))
        self.work_mgr.remove_pending_target(self.test_dir, "high/unit_a.md")
        result = adapter.await_role(handle)
        self.assertEqual(result.role, "high")
        self.assertEqual(result.status, "clean")
