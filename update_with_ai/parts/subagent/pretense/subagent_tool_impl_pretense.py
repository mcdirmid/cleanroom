"""Pretense state machine, fake synthesis, unit tests, and fuzzing for SubagentToolRunner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from update_with_ai.parts.subagent.lib import subagent_coordinator, subagent_tool
from update_with_ai.parts.subagent.lib.subagent_tool import SubagentToolRunner


@dataclass
class SubagentToolState:
    """Canonical model state for SubagentToolRunner."""
    converged: bool = True
    executed_commands: List[Tuple[str, ...]] = field(default_factory=list)


class SubagentToolStateMachine(StateMachine[SubagentToolState]):
    """Unified Pretense State Machine for SubagentToolRunner."""

    def __init__(
        self,
        state: Optional[SubagentToolState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or SubagentToolState(), singletons=singletons)

    @transition(SubagentToolRunner.execute_command)
    def execute_command(
        self,
        ctx: TransitionContext[SubagentToolRunner, [Sequence[str]], int],
    ) -> None:
        ctx.arguments(argv=Domain(strategy=lambda: ()))
        ctx.returns(lambda argv=(): 0 if self.state.converged else 1)
        def provide(res: int, argv: Sequence[str] = ()) -> None:
            self.state.executed_commands.append(tuple(argv))
        ctx.update(provide)

    @transition(SubagentToolRunner.run_orchestrate)
    def run_orchestrate(
        self,
        ctx: TransitionContext[SubagentToolRunner, ..., int],
    ) -> None:
        ctx.arguments(
                    arg_0=Domain(strategy=lambda: 'staging'),
                    arg_1=Domain(strategy=lambda: None),
                    arg_2=Domain(strategy=lambda: None),
                    arg_3=Domain(strategy=lambda: None),
                    arg_4=Domain(strategy=lambda: 50),
                    arg_5=Domain(strategy=lambda: None),
                    arg_6=Domain(strategy=lambda: None),
                    arg_7=Domain(strategy=lambda: None),
                    arg_8=Domain(strategy=lambda: None),
                    arg_9=Domain(strategy=lambda: None),
                    arg_10=Domain(strategy=lambda: None),
                    arg_11=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda *args, **kwargs: 0 if self.state.converged else 1)
        ctx.update(lambda res, *args, **kwargs: None)


proto = SubagentToolStateMachine()


# ==============================================================================
# 2. Synthesized Fake Factory
# ==============================================================================

def make_subagent_tool_fake(
    state: Optional[SubagentToolState] = None,
) -> SubagentToolRunner:
    """Instantiate a synthesized SubagentToolRunner fake."""
    st = state or SubagentToolState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(SubagentToolRunner)


# ==============================================================================
# 3. Deterministic Unit Tests
# ==============================================================================

class TestSubagentToolUnit(unittest.TestCase):
    """Deterministic unit tests validating state machine and synthesized fake."""

    def test_execute_command_converged(self) -> None:
        state = SubagentToolState(converged=True)
        fake = make_subagent_tool_fake(state)
        code = fake.execute_command(["orchestrate", "staging"])
        self.assertEqual(code, 0)
        self.assertEqual(len(state.executed_commands), 1)

    def test_execute_command_failed(self) -> None:
        state = SubagentToolState(converged=False)
        fake = make_subagent_tool_fake(state)
        code = fake.execute_command(["orchestrate", "staging"])
        self.assertEqual(code, 1)

    def test_run_orchestrate(self) -> None:
        fake = make_subagent_tool_fake()
        code = fake.run_orchestrate("staging", target_role="lib")
        self.assertEqual(code, 0)


# ==============================================================================
# 4. Hypothesis Fuzz Tests
# ==============================================================================

class TestSubagentToolFuzz(unittest.TestCase):
    """Hypothesis fuzz tests for tool runner dispatching."""

    @given(
        cmd_args=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
        converged=st.booleans(),
    )
    @settings(max_examples=25)
    def test_execute_command_fuzz(
        self, cmd_args: List[str], converged: bool
    ) -> None:
        state = SubagentToolState(converged=converged)
        fake = make_subagent_tool_fake(state)
        exit_code = fake.execute_command(cmd_args)
        self.assertEqual(exit_code, 0 if converged else 1)
        self.assertIn(tuple(cmd_args), state.executed_commands)


class FakeCoordinator:
    tier = "agent_session"
    def __init__(self, converged: bool = True) -> None:
        self.converged = converged
    def orchestrate(self, *args: Any, **kwargs: Any) -> subagent_coordinator.OrchestrationSummary:
        return subagent_coordinator.OrchestrationSummary(
            is_converged=self.converged,
            total_waves=1,
            submitted_count=1,
            blamed_count=0,
            total_telemetry=subagent_coordinator.TokenUsage(),
            status_message="Converged" if self.converged else "Failed",
        )


class FakeHarnessResolver:
    tier = "agent_session"
    def resolve_harness(self, *args: Any, **kwargs: Any) -> Any:
        class DummyAdapter:
            def dispatch_role(self, dispatch: Any) -> str:
                return "dummy"
            def await_role(self, task_handle: str) -> Any:
                return subagent_coordinator.RoleRoundResult(role="test", status="clean")
            def poll_role(self, task_handle: str) -> Any:
                return self.await_role(task_handle)
            def interrupt_role(self, task_handle: str) -> None:
                pass
        return DummyAdapter()


class TestSubagentToolImplReal(unittest.TestCase):
    """Direct unit tests for subagent_tool_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.subagent.lib import subagent_harness, subagent_tool, subagent_tool_impl

        self.registry = LifecycleRegistry()
        subagent_tool_impl.__initialize__(self.registry)
        self.fake_resolver = FakeHarnessResolver()
        self.fake_coord = FakeCoordinator(converged=True)
        self.registry.register_instance(self.fake_resolver, keys=[subagent_harness.HarnessResolver], tier=agent_session.agent_session)
        self.registry.register_instance(self.fake_coord, keys=[subagent_coordinator.SubagentCoordinator], tier=agent_session.agent_session)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_run_orchestrate(self) -> None:
        from update_with_ai.parts.subagent.lib import subagent_coordinator, subagent_tool
        runner = self.scope.get_singleton(subagent_tool.SubagentToolRunner)
        status = runner.run_orchestrate("pkg_a", harness="simulation")
        self.assertEqual(status, 0)

    def test_execute_command(self) -> None:
        from update_with_ai.parts.subagent.lib import subagent_coordinator, subagent_tool
        runner = self.scope.get_singleton(subagent_tool.SubagentToolRunner)
        self.assertEqual(runner.execute_command(["orchestrate", "pkg_a", "--simulation"]), 0)
        self.assertEqual(runner.execute_command(["pkg_a", "--simulation"]), 0)
