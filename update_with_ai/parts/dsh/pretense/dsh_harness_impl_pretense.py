"""Pretense state machine, fake synthesis, unit tests, and fuzzing for DshHarnessAdapter and DshHarnessManager."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
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


proto = StateMachineProto[DshHarnessState]()


# ==============================================================================
# 1. DshHarnessAdapter Transitions
# ==============================================================================

@proto.transition(DshHarnessAdapter.dispatch_role)
def dispatch_role(): pass

@dispatch_role.arguments
def _(
    state: DshHarnessState,
    this: Any,
    dispatch: RoleDispatch | NotBoundType = NotBound,
) -> Optional[Tuple[RoleDispatch]]:
    if isinstance(dispatch, NotBoundType):
        disp = RoleDispatch(
            role_name="lib",
            workspace_dir="/tmp/ws/lib",
            ready_targets=["//parts/core:core#lib"],
            dir_scope="staging",
            batch_size=1,
        )
    else:
        disp = dispatch
    return (disp,)

@dispatch_role.returns
def _(
    state: DshHarnessState,
    this: Any,
    dispatch: RoleDispatch,
    outcome: object = NotBound,
) -> Optional[Outcome[str]]:
    handle = f"dsh-task-{dispatch.role_name}-{len(state.active_dispatches) + 1}"
    state.active_dispatches[handle] = dispatch

    if isinstance(outcome, Value) and outcome.val.startswith("dsh-task-"):
        return outcome
    if outcome is NotBound:
        return Value(handle)
    return None


@proto.transition(DshHarnessAdapter.poll_role)
def poll_role(): pass

@poll_role.arguments
def _(
    state: DshHarnessState,
    this: Any,
    task_handle: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    h = "dsh-task-1" if isinstance(task_handle, NotBoundType) else str(task_handle)
    return (h,)

@poll_role.returns
def _(
    state: DshHarnessState,
    this: Any,
    task_handle: str,
    outcome: object = NotBound,
) -> Optional[Outcome[Optional[RoleRoundResult]]]:
    if task_handle in state.completed_handles:
        res = state.completed_handles[task_handle]
    elif task_handle in state.active_dispatches:
        res = None
    else:
        res = RoleRoundResult(
            role="lib",
            status="completed",
            submitted_targets=(),
            blamed_targets=(),
            failure_reason=None,
        )

    if isinstance(outcome, Value) and (outcome.val == res or (outcome.val is None and res is None)):
        return outcome
    if outcome is NotBound:
        return Value(res)
    return None


@proto.transition(DshHarnessAdapter.await_role)
def await_role(): pass

@await_role.arguments
def _(
    state: DshHarnessState,
    this: Any,
    task_handle: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    h = "dsh-task-1" if isinstance(task_handle, NotBoundType) else str(task_handle)
    return (h,)

@await_role.returns
def _(
    state: DshHarnessState,
    this: Any,
    task_handle: str,
    outcome: object = NotBound,
) -> Optional[Outcome[RoleRoundResult]]:
    disp = state.active_dispatches.get(
        task_handle,
        RoleDispatch(role_name="lib", workspace_dir="/tmp", ready_targets=[], dir_scope=""),
    )
    result = state.completed_handles.get(
        task_handle,
        RoleRoundResult(
            role=disp.role_name,
            status="completed",
            submitted_targets=tuple(disp.ready_targets),
            blamed_targets=(),
            failure_reason=None,
        ),
    )
    state.completed_handles[task_handle] = result

    if isinstance(outcome, Value) and outcome.val.status == result.status:
        return outcome
    if outcome is NotBound:
        return Value(result)
    return None


@proto.transition(DshHarnessAdapter.interrupt_role)
def interrupt_role(): pass

@interrupt_role.arguments
def _(
    state: DshHarnessState,
    this: Any,
    task_handle: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    h = "dsh-task-1" if isinstance(task_handle, NotBoundType) else str(task_handle)
    return (h,)

@interrupt_role.returns
def _(
    state: DshHarnessState,
    this: Any,
    task_handle: str,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.interrupted_handles.append(task_handle)
    if isinstance(outcome, Value) and outcome.val is None:
        return outcome
    if outcome is NotBound:
        return Value(None)
    return None


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
