"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceToolRunner."""

from __future__ import annotations

from dataclasses import dataclass, field
import io
import os
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.workspace_cli.lib.cli_tool import WorkspaceToolRunner


@dataclass
class ToolRunnerState:
    """Canonical model state for WorkspaceToolRunner."""
    exit_code: int = 0


proto = StateMachineProto[ToolRunnerState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_tool_runner_data(): pass

@seed_tool_runner_data.arguments
def _(
    state: ToolRunnerState,
    this: Any,
    exit_code: int | NotBoundType = NotBound,
) -> Optional[Tuple[int]]:
    e = 0 if isinstance(exit_code, NotBoundType) else int(exit_code)
    return (e,)

@seed_tool_runner_data.provide
def _(
    state: ToolRunnerState,
    this: Any,
    exit_code: int,
    result: None = None,
) -> None:
    state.exit_code = exit_code


# ==============================================================================
# 2. Tool Runner Transitions
# ==============================================================================

@proto.transition(WorkspaceToolRunner.execute_command)
def execute_command(): pass

@execute_command.arguments
def _(
    state: ToolRunnerState,
    this: Any,
    argv: Sequence[str] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[str]]]:
    a = ("get_work",) if isinstance(argv, NotBoundType) else tuple(argv)
    return (a,)

@execute_command.returns
def _(
    state: ToolRunnerState,
    this: Any,
    argv: Sequence[str],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    return Value(state.exit_code)


@proto.transition(WorkspaceToolRunner.run_get_work)
def run_get_work(): pass

@run_get_work.arguments
def _(
    state: ToolRunnerState,
    this: Any,
    dir_scope: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
    force: bool | NotBoundType = NotBound,
    batch_size: Optional[int] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str], Optional[str], bool, Optional[int]]]:
    ds = None if isinstance(dir_scope, NotBoundType) else dir_scope
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    f = False if isinstance(force, NotBoundType) else bool(force)
    bs = None if isinstance(batch_size, NotBoundType) else batch_size
    return (ds, rr, f, bs)

@run_get_work.returns
def _(
    state: ToolRunnerState,
    this: Any,
    dir_scope: Optional[str],
    repo_root: Optional[str],
    force: bool,
    batch_size: Optional[int],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    return Value(state.exit_code)


@proto.transition(WorkspaceToolRunner.run_check_files)
def run_check_files(): pass

@run_check_files.arguments
def _(
    state: ToolRunnerState,
    this: Any,
    target: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str], Optional[str]]]:
    t = None if isinstance(target, NotBoundType) else target
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    return (t, rr)

@run_check_files.returns
def _(
    state: ToolRunnerState,
    this: Any,
    target: Optional[str],
    repo_root: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    return Value(state.exit_code)


@proto.transition(WorkspaceToolRunner.run_submit)
def run_submit(): pass

@run_submit.arguments
def _(
    state: ToolRunnerState,
    this: Any,
    target: str | NotBoundType = NotBound,
    summary: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
    no_verify: bool | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[str], Optional[str], bool]]:
    t = "lib/foo.py" if isinstance(target, NotBoundType) else str(target)
    s = None if isinstance(summary, NotBoundType) else summary
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    nv = False if isinstance(no_verify, NotBoundType) else bool(no_verify)
    return (t, s, rr, nv)

@run_submit.returns
def _(
    state: ToolRunnerState,
    this: Any,
    target: str,
    summary: Optional[str],
    repo_root: Optional[str],
    no_verify: bool,
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    return Value(state.exit_code)


@proto.transition(WorkspaceToolRunner.run_blame)
def run_blame(): pass

@run_blame.arguments
def _(
    state: ToolRunnerState,
    this: Any,
    culprit_file: str | NotBoundType = NotBound,
    critique: str | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, Optional[str]]]:
    cf = "low/foo.pyi" if isinstance(culprit_file, NotBoundType) else str(culprit_file)
    c = "critique" if isinstance(critique, NotBoundType) else str(critique)
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    return (cf, c, rr)

@run_blame.returns
def _(
    state: ToolRunnerState,
    this: Any,
    culprit_file: str,
    critique: str,
    repo_root: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    return Value(state.exit_code)


@proto.transition(WorkspaceToolRunner.run_fail)
def run_fail(): pass

@run_fail.arguments
def _(
    state: ToolRunnerState,
    this: Any,
    file_path: str | NotBoundType = NotBound,
    reason: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    fp = "lib/foo.py" if isinstance(file_path, NotBoundType) else str(file_path)
    r = None if isinstance(reason, NotBoundType) else reason
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    return (fp, r, rr)

@run_fail.returns
def _(
    state: ToolRunnerState,
    this: Any,
    file_path: str,
    reason: Optional[str],
    repo_root: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    return Value(state.exit_code)


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
