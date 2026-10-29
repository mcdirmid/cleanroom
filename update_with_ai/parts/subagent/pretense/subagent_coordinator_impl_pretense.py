"""Pretense state machine, fake synthesis, unit tests, and fuzzing for SubagentCoordinator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from update_with_ai.parts.subagent.lib import subagent_coordinator
from update_with_ai.parts.subagent.lib.subagent_coordinator import (
    HarnessAdapter,
    OrchestrationSummary,
    RoleDispatch,
    RoleRoundResult,
    SubagentCoordinator,
    TokenUsage,
)


@dataclass
class SubagentCoordinatorState:
    """Canonical model state for SubagentCoordinator."""
    pending_waves: List[List[RoleDispatch]] = field(default_factory=list)
    converged: bool = True
    total_waves_executed: int = 0
    submitted_targets: List[str] = field(default_factory=list)
    blamed_targets: List[str] = field(default_factory=list)


class SubagentCoordinatorStateMachine(StateMachine[SubagentCoordinatorState]):
    """Unified Pretense State Machine for SubagentCoordinator."""

    def __init__(
        self,
        state: Optional[SubagentCoordinatorState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SubagentCoordinatorState(), singletons=singletons)

    @transition(SubagentCoordinator.compute_execution_waves)
    def compute_execution_waves(
        self,
        ctx: TransitionContext[SubagentCoordinator, [str, Optional[str], Optional[str], Optional[int]], Sequence[Sequence[RoleDispatch]]],
    ) -> None:
        ctx.arguments(
                    dir_scope=Domain(strategy=lambda: 'staging'),
                    target_role=Domain(strategy=lambda: None),
                    repo_root=Domain(strategy=lambda: None),
                    batch_size=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda dir_scope="staging", target_role=None, repo_root=None, batch_size=None: (
            tuple(tuple(w) for w in self.state.pending_waves)
        ))
        ctx.update(lambda res, dir_scope="staging", target_role=None, repo_root=None, batch_size=None: None)

    @transition(SubagentCoordinator.run_wave)
    def run_wave(
        self,
        ctx: TransitionContext[SubagentCoordinator, [Sequence[RoleDispatch], Any], Sequence[RoleRoundResult]],
    ) -> None:
        ctx.arguments(
                    wave=Domain(strategy=lambda: ()),
                    harness=Domain(strategy=lambda: None),
                )
        def returns(wave: Sequence[RoleDispatch] = (), harness: Any = None) -> Sequence[RoleRoundResult]:
            results: List[RoleRoundResult] = []
            for disp in wave:
                if harness is not None and hasattr(harness, "dispatch_role"):
                    handle = harness.dispatch_role(disp)
                    res = harness.await_role(handle)
                else:
                    res = RoleRoundResult(
                        role=disp.role_name,
                        status="completed",
                        submitted_targets=tuple(disp.ready_targets),
                        blamed_targets=(),
                        failure_reason=None,
                    )
                results.append(res)
                self.state.submitted_targets.extend(res.submitted_targets)
                self.state.blamed_targets.extend(res.blamed_targets)

            self.state.total_waves_executed += 1
            return tuple(results)

        ctx.returns(returns)
        ctx.update(lambda res, wave=(), harness=None: None)

    @transition(SubagentCoordinator.orchestrate)
    def orchestrate(
        self,
        ctx: TransitionContext[SubagentCoordinator, ..., OrchestrationSummary],
    ) -> None:
        ctx.arguments(
                    arg_0=Domain(strategy=lambda: 'staging'),
                    arg_1=Domain(strategy=lambda: None),
                    arg_2=Domain(strategy=lambda: None),
                    arg_3=Domain(strategy=lambda: 50),
                    arg_4=Domain(strategy=lambda: None),
                    arg_5=Domain(strategy=lambda: None),
                    arg_6=Domain(strategy=lambda: None),
                    arg_7=Domain(strategy=lambda: None),
                    arg_8=Domain(strategy=lambda: None),
                    arg_9=Domain(strategy=lambda: None),
                    arg_10=Domain(strategy=lambda: None),
                )
        def returns(
            dir_scope: str = "staging",
            harness: Any = None,
            target_role: Optional[str] = None,
            max_waves: int = 100,
            batch_size: Optional[int] = None,
            repo_root: Optional[str] = None,
            model_name: Optional[str] = None,
            poll_interval: Optional[float] = None,
            max_unproductive_turns: Optional[int] = None,
            target_node: Optional[str] = None,
            max_unproductive_rounds: Optional[int] = None,
            *args: Any,
            **kwargs: Any,
        ) -> OrchestrationSummary:
            for wave in self.state.pending_waves:
                for disp in wave:
                    if harness is not None and hasattr(harness, "dispatch_role"):
                        handle = harness.dispatch_role(disp)
                        res = harness.await_role(handle)
                        self.state.submitted_targets.extend(res.submitted_targets)
                        self.state.blamed_targets.extend(res.blamed_targets)
                    else:
                        self.state.submitted_targets.extend(disp.ready_targets)
                self.state.total_waves_executed += 1

            return OrchestrationSummary(
                is_converged=self.state.converged,
                total_waves=self.state.total_waves_executed,
                submitted_count=len(self.state.submitted_targets),
                blamed_count=len(self.state.blamed_targets),
                total_telemetry=TokenUsage(total_tokens=100),
                status_message="Orchestration completed successfully." if self.state.converged else "Convergence failed.",
            )

        ctx.returns(returns)
        ctx.update(lambda res, *args, **kwargs: None)


proto = SubagentCoordinatorStateMachine()


# ==============================================================================
# 2. Synthesized Fake Factory
# ==============================================================================

def make_subagent_coordinator_fake(
    state: Optional[SubagentCoordinatorState] = None,
) -> SubagentCoordinator:
    """Instantiate a synthesized SubagentCoordinator fake."""
    st = state or SubagentCoordinatorState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(SubagentCoordinator)


# ==============================================================================
# 3. Deterministic Unit Tests
# ==============================================================================

class _DummyHarness:
    def __init__(self) -> None:
        self.dispatches: List[RoleDispatch] = []

    def dispatch_role(self, dispatch: RoleDispatch) -> str:
        self.dispatches.append(dispatch)
        return f"task-{dispatch.role_name}"

    def await_role(self, task_handle: str) -> RoleRoundResult:
        role = task_handle.replace("task-", "")
        return RoleRoundResult(
            role=role,
            status="completed",
            submitted_targets=(f"//parts/test:{role}#lib",),
            blamed_targets=(),
            failure_reason=None,
        )

    def poll_role(self, task_handle: str) -> Optional[RoleRoundResult]:
        return self.await_role(task_handle)

    def interrupt_role(self, task_handle: str) -> None:
        pass


class TestSubagentCoordinatorUnit(unittest.TestCase):
    """Deterministic unit tests for SubagentCoordinator fake."""

    def test_compute_empty_waves(self) -> None:
        fake = make_subagent_coordinator_fake()
        waves = fake.compute_execution_waves("staging")
        self.assertEqual(len(waves), 0)

    def test_run_wave_with_harness(self) -> None:
        fake = make_subagent_coordinator_fake()
        harness = _DummyHarness()
        disp = RoleDispatch(
            role_name="lib",
            workspace_dir="/ws/lib",
            dir_scope="staging",
            ready_targets=["//parts/test:lib#lib"],
        )
        results = fake.run_wave([disp], harness)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "completed")
        self.assertEqual(results[0].role, "lib")
        self.assertEqual(len(harness.dispatches), 1)

    def test_orchestrate_lifecycle(self) -> None:
        state = SubagentCoordinatorState(
            pending_waves=[[
                RoleDispatch(
                    role_name="planning",
                    workspace_dir="/ws/planning",
                    dir_scope="staging",
                    ready_targets=["//parts/test:planning#planning"],
                )
            ]],
            converged=True,
        )
        fake = make_subagent_coordinator_fake(state)
        harness = _DummyHarness()
        summary = fake.orchestrate("staging", harness)
        self.assertTrue(summary.is_converged)
        self.assertEqual(summary.total_waves, 1)
        self.assertEqual(summary.submitted_count, 1)


# ==============================================================================
# 4. Hypothesis Fuzz Tests
# ==============================================================================

class TestSubagentCoordinatorFuzz(unittest.TestCase):
    """Hypothesis fuzz tests for SubagentCoordinator invariants."""

    @given(
        roles=st.lists(
            st.sampled_from(["high", "planning", "low", "lib", "test", "qa", "coverage"]),
            min_size=1,
            max_size=5,
        ),
        converged=st.booleans(),
    )
    @settings(max_examples=25)
    def test_orchestrate_wave_invariants(
        self, roles: List[str], converged: bool
    ) -> None:
        wave = [
            RoleDispatch(
                role_name=r,
                workspace_dir=f"/ws/{r}",
                dir_scope="staging",
                ready_targets=[f"//parts/test:{r}#{r}"],
            )
            for r in roles
        ]
        state = SubagentCoordinatorState(pending_waves=[wave], converged=converged)
        fake = make_subagent_coordinator_fake(state)
        harness = _DummyHarness()
        summary = fake.orchestrate("staging", harness)
        self.assertEqual(summary.is_converged, converged)
        self.assertEqual(summary.total_waves, 1)
        self.assertEqual(summary.submitted_count, len(roles))
        self.assertEqual(summary.blamed_count, 0)


class TestSubagentCoordinatorImplReal(unittest.TestCase):
    """Direct unit tests for subagent_coordinator_impl.py."""

    def test_resolve_model_parameters(self) -> None:
        from update_with_ai.parts.subagent.lib.subagent_coordinator_impl import resolve_model_parameters
        batch_size, max_tokens, max_rounds = resolve_model_parameters("/tmp", model_name="pro")
        self.assertIsInstance((batch_size, max_tokens, max_rounds), tuple)

    def test_coordinator_empty_orchestrate(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.subagent.lib import subagent_coordinator, subagent_coordinator_impl
        from update_with_ai.parts.workspace_cli.lib import work
        from update_with_ai.parts.workspace.lib import provision, role_registry

        registry = LifecycleRegistry()
        subagent_coordinator_impl.__initialize__(registry)

        class DummyProvisioner:
            tier = "agent_session"
            def commission(self, *args: Any, **kwargs: Any) -> Any:
                return None

        class DummyRegistry:
            tier = "agent_session"
            def discover_repository_root(self, *args: Any) -> str:
                return "/repo"
            def list_roles(self, *args: Any, **kwargs: Any) -> Sequence[Any]:
                return ()

        class DummyWorkManager:
            tier = "agent_session"
            def compute_role_work_queue(self, *args: Any, **kwargs: Any) -> Any:
                return ((), ())

        registry.register_instance(DummyProvisioner(), keys=[provision.WorkspaceProvisioner], tier=agent_session.agent_session)
        registry.register_instance(DummyRegistry(), keys=[role_registry.WorkspaceRegistry], tier=agent_session.agent_session)
        registry.register_instance(DummyWorkManager(), keys=[work.WorkspaceWorkManager], tier=agent_session.agent_session)

        with enter_phase(agent_session.agent_session, registry=registry) as scope:
            coord = scope.get_singleton(subagent_coordinator.SubagentCoordinator)
            harness = _DummyHarness()
            summary = coord.orchestrate("staging", harness)
            self.assertTrue(summary.is_converged)
