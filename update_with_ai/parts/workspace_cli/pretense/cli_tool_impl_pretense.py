"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceToolRunner."""

from __future__ import annotations

from dataclasses import dataclass, field
import io
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from update_with_ai.parts.workspace_cli.lib.cli_tool import WorkspaceToolRunner


@dataclass
class ToolRunnerState:
    """Canonical model state for WorkspaceToolRunner."""
    exit_code: int = 0


class WorkspaceToolRunnerStateMachine(StateMachine[ToolRunnerState]):
    """Unified Pretense State Machine for WorkspaceToolRunner."""

    def __init__(
        self,
        state: Optional[ToolRunnerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or ToolRunnerState(), singletons=singletons)

    @transition.seeding(name="seed_tool_runner_data")
    def seed_tool_runner_data(
        self,
        ctx: TransitionContext[Any, [int], None],
    ) -> None:
        ctx.arguments(exit_code=Domain(strategy=lambda: 0))
        ctx.returns(lambda exit_code=0: None)
        ctx.update(lambda res, exit_code=0: setattr(self.state, "exit_code", int(exit_code)))

    @transition(WorkspaceToolRunner.execute_command)
    def execute_command(
        self,
        ctx: TransitionContext[WorkspaceToolRunner, [Sequence[str]], int],
    ) -> None:
        ctx.arguments(argv=Domain(strategy=lambda: ('get_work',)))
        ctx.returns(lambda argv=("get_work",): self.state.exit_code)
        ctx.update(lambda res, argv=("get_work",): None)

    @transition(WorkspaceToolRunner.run_get_work)
    def run_get_work(
        self,
        ctx: TransitionContext[WorkspaceToolRunner, [Optional[str], Optional[str], bool, Optional[int]], int],
    ) -> None:
        ctx.arguments(
                    dir_scope=Domain(strategy=lambda: None),
                    repo_root=Domain(strategy=lambda: None),
                    force=Domain(strategy=lambda: False),
                    batch_size=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda dir_scope=None, repo_root=None, force=False, batch_size=None: self.state.exit_code)
        ctx.update(lambda res, dir_scope=None, repo_root=None, force=False, batch_size=None: None)

    @transition(WorkspaceToolRunner.run_check_files)
    def run_check_files(
        self,
        ctx: TransitionContext[WorkspaceToolRunner, [Optional[str], Optional[str]], int],
    ) -> None:
        ctx.arguments(
                    target=Domain(strategy=lambda: None),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda target=None, repo_root=None: self.state.exit_code)
        ctx.update(lambda res, target=None, repo_root=None: None)

    @transition(WorkspaceToolRunner.run_submit)
    def run_submit(
        self,
        ctx: TransitionContext[WorkspaceToolRunner, [str, Optional[str], Optional[str], bool], int],
    ) -> None:
        ctx.arguments(
                    target=Domain(strategy=lambda: 'lib/foo.py'),
                    summary=Domain(strategy=lambda: None),
                    repo_root=Domain(strategy=lambda: None),
                    no_verify=Domain(strategy=lambda: False),
                )
        ctx.returns(lambda target="lib/foo.py", summary=None, repo_root=None, no_verify=False: self.state.exit_code)
        ctx.update(lambda res, target="lib/foo.py", summary=None, repo_root=None, no_verify=False: None)

    @transition(WorkspaceToolRunner.run_blame)
    def run_blame(
        self,
        ctx: TransitionContext[WorkspaceToolRunner, [str, str, Optional[str]], int],
    ) -> None:
        ctx.arguments(
                    culprit_file=Domain(strategy=lambda: 'low/foo.pyi'),
                    critique=Domain(strategy=lambda: 'critique'),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda culprit_file="low/foo.pyi", critique="critique", repo_root=None: self.state.exit_code)
        ctx.update(lambda res, culprit_file="low/foo.pyi", critique="critique", repo_root=None: None)

    @transition(WorkspaceToolRunner.run_fail)
    def run_fail(
        self,
        ctx: TransitionContext[WorkspaceToolRunner, [str, Optional[str], Optional[str]], int],
    ) -> None:
        ctx.arguments(
                    file_path=Domain(strategy=lambda: 'lib/foo.py'),
                    reason=Domain(strategy=lambda: None),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda file_path="lib/foo.py", reason=None, repo_root=None: self.state.exit_code)
        ctx.update(lambda res, file_path="lib/foo.py", reason=None, repo_root=None: None)


proto = WorkspaceToolRunnerStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_tool_runner_fake(state: Optional[ToolRunnerState] = None) -> WorkspaceToolRunner:
    """Instantiate a synthesized WorkspaceToolRunner fake."""
    st = state or ToolRunnerState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspaceToolRunner)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspaceToolRunnerUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspaceToolRunner fake."""

    def setUp(self) -> None:
        self.state = ToolRunnerState(exit_code=0)
        self.sm = proto.make_state_machine(self.state)
        self.fake: WorkspaceToolRunner = self.sm.as_fake(WorkspaceToolRunner)

    def test_execute_command(self) -> None:
        self.assertEqual(self.fake.execute_command(["get_work"]), 0)
        self.assertEqual(self.fake.run_get_work(), 0)
        self.assertEqual(self.fake.run_check_files(), 0)
        self.assertEqual(self.fake.run_submit("lib/foo.py"), 0)
        self.assertEqual(self.fake.run_blame("low/foo.pyi", "critique"), 0)
        self.assertEqual(self.fake.run_fail("lib/foo.py"), 0)


class TestWorkspaceToolRunnerImplReal(unittest.TestCase):
    """Direct unit tests for cli_tool_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.workspace_cli.lib import cli_tool, cli_tool_impl, commands

        self.registry = LifecycleRegistry()

        class DummyCommandHandler:
            tier = agent_session.agent_session
            def run_get_work(self, *args: Any, **kwargs: Any) -> int:
                return 0
            def run_check_files(self, *args: Any, **kwargs: Any) -> int:
                return 0
            def run_submit(self, *args: Any, **kwargs: Any) -> int:
                return 0
            def run_blame(self, *args: Any, **kwargs: Any) -> int:
                return 0
            def run_fail(self, *args: Any, **kwargs: Any) -> int:
                return 0
            def run_clean(self, *args: Any, **kwargs: Any) -> int:
                return 0

        self.registry.register_instance(
            DummyCommandHandler(),
            keys=[commands.WorkspaceCommandHandler],
            tier=agent_session.agent_session,
        )
        cli_tool_impl.__initialize__(self.registry)

        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.runner = self.scope.get_singleton(cli_tool_impl.WorkspaceToolRunner)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_execute_commands_dispatch(self) -> None:
        self.assertEqual(self.runner.execute_command(["get_work"]), 0)
        self.assertEqual(self.runner.execute_command(["check_files"]), 0)
        self.assertEqual(self.runner.execute_command(["submit", "lib/foo.py", "summary"]), 0)
        self.assertEqual(self.runner.execute_command(["blame", "low/foo.pyi", "critique"]), 0)
        self.assertEqual(self.runner.execute_command(["feedback", "low/foo.pyi", "critique"]), 0)
        self.assertEqual(self.runner.execute_command(["fail", "lib/foo.py", "blocked"]), 0)

    def test_delegated_methods(self) -> None:
        self.assertEqual(self.runner.run_get_work(), 0)
        self.assertEqual(self.runner.run_check_files(), 0)
        self.assertEqual(self.runner.run_submit("lib/foo.py"), 0)
        self.assertEqual(self.runner.run_blame("low/foo.pyi", "critique"), 0)
        self.assertEqual(self.runner.run_fail("lib/foo.py"), 0)


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspaceToolRunnerFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspaceToolRunner."""

    @settings(max_examples=30)
    @given(
        code=st.sampled_from([0, 1, 2]),
    )
    def test_tool_runner_invariants(self, code: int) -> None:
        state = ToolRunnerState(exit_code=code)
        sm = proto.make_state_machine(state)
        fake = sm.as_fake(WorkspaceToolRunner)

        self.assertEqual(fake.execute_command(["get_work"]), code)
