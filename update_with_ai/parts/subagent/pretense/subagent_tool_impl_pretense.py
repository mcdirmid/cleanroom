"""Pretense state machine, fake synthesis, unit tests, and fuzzing for SubagentToolRunner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.subagent.lib import subagent_coordinator, subagent_tool
from update_with_ai.parts.subagent.lib.subagent_tool import SubagentToolRunner


@dataclass
class SubagentToolState:
    """Canonical model state for SubagentToolRunner."""
    converged: bool = True
    executed_commands: List[Tuple[str, ...]] = field(default_factory=list)


proto = StateMachineProto[SubagentToolState]()


# ==============================================================================
# 1. SubagentToolRunner Transitions
# ==============================================================================

@proto.transition(SubagentToolRunner.execute_command)
def execute_command(): pass

@execute_command.arguments
def _(
    state: SubagentToolState,
    this: Any,
    argv: Sequence[str] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[str]]]:
    args = () if isinstance(argv, NotBoundType) else tuple(argv)
    return (args,)

@execute_command.returns
def _(
    state: SubagentToolState,
    this: Any,
    argv: Sequence[str],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    state.executed_commands.append(tuple(argv))
    ret = 0 if state.converged else 1
    if isinstance(outcome, Value) and outcome.val == ret:
        return outcome
    if outcome is NotBound:
        return Value(ret)
    return None


@proto.transition(SubagentToolRunner.run_orchestrate)
def run_orchestrate(): pass

@run_orchestrate.arguments
def _(
    state: SubagentToolState,
    this: Any,
    dir_scope: str | NotBoundType = NotBound,
    target_role: Optional[str] | NotBoundType = NotBound,
    harness: Optional[str] | NotBoundType = NotBound,
    model: Optional[str] | NotBoundType = NotBound,
    max_waves: int | NotBoundType = NotBound,
    batch_size: Optional[int] | NotBoundType = NotBound,
    timeout: Optional[float] | NotBoundType = NotBound,
    max_context_tokens: Optional[int] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
    max_unproductive_turns: Optional[int] | NotBoundType = NotBound,
    target_node: Optional[str] | NotBoundType = NotBound,
    max_unproductive_rounds: Optional[int] | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[str], Optional[str], Optional[str], int, Optional[int], Optional[float], Optional[int], Optional[str], Optional[int], Optional[str], Optional[int]]]:
    ds = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    tr = None if isinstance(target_role, NotBoundType) else target_role
    h = None if isinstance(harness, NotBoundType) else harness
    m = None if isinstance(model, NotBoundType) else model
    mw = 50 if isinstance(max_waves, NotBoundType) else int(max_waves)
    bs = None if isinstance(batch_size, NotBoundType) else batch_size
    to = None if isinstance(timeout, NotBoundType) else timeout
    mct = None if isinstance(max_context_tokens, NotBoundType) else max_context_tokens
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    mut = None if isinstance(max_unproductive_turns, NotBoundType) else max_unproductive_turns
    tn = None if isinstance(target_node, NotBoundType) else target_node
    mur = None if isinstance(max_unproductive_rounds, NotBoundType) else max_unproductive_rounds
    return (ds, tr, h, m, mw, bs, to, mct, rr, mut, tn, mur)

@run_orchestrate.returns
def _(
    state: SubagentToolState,
    this: Any,
    dir_scope: str,
    target_role: Optional[str],
    harness: Optional[str],
    model: Optional[str],
    max_waves: int,
    batch_size: Optional[int],
    timeout: Optional[float],
    max_context_tokens: Optional[int],
    repo_root: Optional[str],
    max_unproductive_turns: Optional[int],
    target_node: Optional[str],
    max_unproductive_rounds: Optional[int],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    ret = 0 if state.converged else 1
    if isinstance(outcome, Value) and outcome.val == ret:
        return outcome
    if outcome is NotBound:
        return Value(ret)
    return None


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
