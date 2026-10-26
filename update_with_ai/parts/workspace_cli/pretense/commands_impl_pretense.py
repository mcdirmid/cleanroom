"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceCommandHandler."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Dict, List, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.workspace_cli.lib.commands import (
    WorkspaceCommandHandler,
)


@dataclass
class CommandHandlerState:
    """Canonical model state for WorkspaceCommandHandler."""
    check_files_exit_code: int = 0
    submitted_targets: PretenseSet[str] = field(default_factory=PretenseSet)
    blamed_files: PretenseDict[str, str] = field(default_factory=PretenseDict)
    failed_files: PretenseDict[str, str] = field(default_factory=PretenseDict)


proto = StateMachineProto[CommandHandlerState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_command_state(): pass

@seed_command_state.arguments
def _(
    state: CommandHandlerState,
    this: Any,
    check_files_exit_code: int | NotBoundType = NotBound,
) -> Optional[Tuple[int]]:
    code = 0 if isinstance(check_files_exit_code, NotBoundType) else int(check_files_exit_code)
    return (code,)

@seed_command_state.provide
def _(
    state: CommandHandlerState,
    this: Any,
    check_files_exit_code: int,
    result: None = None,
) -> None:
    state.check_files_exit_code = check_files_exit_code


# ==============================================================================
# 2. WorkspaceCommandHandler Transitions
# ==============================================================================

@proto.transition(WorkspaceCommandHandler.run_get_work)
def run_get_work(): pass

@run_get_work.arguments
def _(
    state: CommandHandlerState,
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
    state: CommandHandlerState,
    this: Any,
    dir_scope: Optional[str],
    repo_root: Optional[str],
    force: bool,
    batch_size: Optional[int],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    expected = 0
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(WorkspaceCommandHandler.run_check_files)
def run_check_files(): pass

@run_check_files.arguments
def _(
    state: CommandHandlerState,
    this: Any,
    target: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str], Optional[str]]]:
    t = None if isinstance(target, NotBoundType) else target
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    return (t, rr)

@run_check_files.returns
def _(
    state: CommandHandlerState,
    this: Any,
    target: Optional[str],
    repo_root: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    expected = state.check_files_exit_code
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(WorkspaceCommandHandler.run_submit)
def run_submit(): pass

@run_submit.arguments
def _(
    state: CommandHandlerState,
    this: Any,
    target: str | NotBoundType = NotBound,
    summary: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
    no_verify: bool | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[str], Optional[str], bool]]:
    t = "lib/module.py" if isinstance(target, NotBoundType) else str(target)
    s = "Implemented" if isinstance(summary, NotBoundType) else summary
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    nv = False if isinstance(no_verify, NotBoundType) else bool(no_verify)
    return (t, s, rr, nv)

@run_submit.returns
def _(
    state: CommandHandlerState,
    this: Any,
    target: str,
    summary: Optional[str],
    repo_root: Optional[str],
    no_verify: bool,
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    expected = state.check_files_exit_code if not no_verify else 0
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@run_submit.provide
def _(
    state: CommandHandlerState,
    this: Any,
    target: str,
    summary: Optional[str],
    repo_root: Optional[str],
    no_verify: bool,
    result: int,
) -> None:
    if result == 0:
        state.submitted_targets.add(target)


@proto.transition(WorkspaceCommandHandler.run_blame)
def run_blame(): pass

@run_blame.arguments
def _(
    state: CommandHandlerState,
    this: Any,
    culprit_file: str | NotBoundType = NotBound,
    critique: str | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, Optional[str]]]:
    cf = "lib/culprit.py" if isinstance(culprit_file, NotBoundType) else str(culprit_file)
    c = "Missing error check" if isinstance(critique, NotBoundType) else str(critique)
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    return (cf, c, rr)

@run_blame.returns
def _(
    state: CommandHandlerState,
    this: Any,
    culprit_file: str,
    critique: str,
    repo_root: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    expected = 0 if "\n" not in critique else 1
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@run_blame.provide
def _(
    state: CommandHandlerState,
    this: Any,
    culprit_file: str,
    critique: str,
    repo_root: Optional[str],
    result: int,
) -> None:
    if result == 0:
        state.blamed_files[culprit_file] = critique


@proto.transition(WorkspaceCommandHandler.run_fail)
def run_fail(): pass

@run_fail.arguments
def _(
    state: CommandHandlerState,
    this: Any,
    file_path: str | NotBoundType = NotBound,
    reason: Optional[str] | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    fp = "lib/module.py" if isinstance(file_path, NotBoundType) else str(file_path)
    r = "Verification failed" if isinstance(reason, NotBoundType) or reason is None else str(reason)
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    return (fp, r, rr)

@run_fail.returns
def _(
    state: CommandHandlerState,
    this: Any,
    file_path: str,
    reason: Optional[str],
    repo_root: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    expected = 0
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@run_fail.provide
def _(
    state: CommandHandlerState,
    this: Any,
    file_path: str,
    reason: Optional[str],
    repo_root: Optional[str],
    result: int,
) -> None:
    if reason:
        state.failed_files[file_path] = reason


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_command_handler_fake(state: Optional[CommandHandlerState] = None) -> WorkspaceCommandHandler:
    """Instantiate a synthesized WorkspaceCommandHandler fake."""
    st = state or CommandHandlerState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspaceCommandHandler)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspaceCommandHandlerUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspaceCommandHandler fake."""

    def setUp(self) -> None:
        self.state = CommandHandlerState()
        self.fake = make_command_handler_fake(self.state)

    def test_run_get_work_and_check_files(self) -> None:
        self.assertEqual(self.fake.run_get_work(), 0)
        self.assertEqual(self.fake.run_check_files(), 0)

    def test_run_submit_success(self) -> None:
        code = self.fake.run_submit("lib/core.py", "Added core")
        self.assertEqual(code, 0)
        self.assertIn("lib/core.py", self.state.submitted_targets)

    def test_run_blame_success(self) -> None:
        code = self.fake.run_blame("lib/culprit.py", "Defect critique")
        self.assertEqual(code, 0)
        self.assertEqual(self.state.blamed_files["lib/culprit.py"], "Defect critique")

    def test_run_blame_rejects_newlines(self) -> None:
        code = self.fake.run_blame("lib/culprit.py", "Line 1\nLine 2")
        self.assertEqual(code, 1)


class TestWorkspaceCommandHandlerImplReal(unittest.TestCase):
    """Direct unit tests for commands_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.control.lib import attribution, submit
        from update_with_ai.parts.metadata.lib import src_metadata_impl
        from update_with_ai.parts.workspace.lib import role_registry_impl, roles_impl
        from update_with_ai.parts.workspace_cli.lib import check_impl, commands, commands_impl, pending_impl

        self.registry = LifecycleRegistry()
        src_metadata_impl.__initialize__(self.registry)
        roles_impl.__initialize__(self.registry)
        role_registry_impl.__initialize__(self.registry)
        pending_impl.__initialize__(self.registry)
        check_impl.__initialize__(self.registry)
        commands_impl.__initialize__(self.registry)

        class DummySubmitCoordinator:
            tier = agent_session.agent_session
            def submit_target_file(self, *args: Any, **kwargs: Any) -> Any:
                from update_with_ai.parts.control.lib import submit
                return submit.SubmissionOutcome(accepted=True, message="OK")
            def resolve_submit_target(self, target: str, repo_root: str, role_name: str, dir_scope: str = "staging") -> Tuple[Optional[str], Optional[str]]:
                if os.path.isfile(target):
                    return target, os.path.splitext(os.path.basename(target))[0]
                cand = os.path.join(repo_root, target)
                if os.path.isfile(cand):
                    return cand, os.path.splitext(os.path.basename(cand))[0]
                return None, None
            def parse_unit_from_file_path(self, file_path: str, repo_root: str) -> Tuple[str, str, str]:
                rel = os.path.relpath(file_path, repo_root).replace("\\", "/") if file_path.startswith(repo_root) else file_path.replace("\\", "/")
                fname = os.path.basename(rel)
                stem = os.path.splitext(fname)[0]
                part_dir = os.path.dirname(os.path.dirname(rel))
                return part_dir, stem, ""

        class DummyAttributionCoordinator:
            tier = agent_session.agent_session
            def blame_culprit_file(self, *args: Any, **kwargs: Any) -> Any:
                from update_with_ai.parts.control.lib import attribution
                return attribution.AttributionOutcome(accepted=True, message="Blamed", affected_nodes=())
            def fail_target_file(self, *args: Any, **kwargs: Any) -> Any:
                from update_with_ai.parts.control.lib import attribution
                return attribution.AttributionOutcome(accepted=True, message="Failed", affected_nodes=())

        self.registry.register_instance(
            DummySubmitCoordinator(),
            keys=[submit.SubmissionCoordinator],
            tier=agent_session.agent_session,
        )
        self.registry.register_instance(
            DummyAttributionCoordinator(),
            keys=[attribution.AttributionCoordinator],
            tier=agent_session.agent_session,
        )

        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.handler = self.scope.get_singleton(commands_impl.WorkspaceCommandHandler)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_run_blame_and_fail(self) -> None:
        import os
        import tempfile
        from update_with_ai.parts.workspace_cli.lib import check_impl

        with tempfile.TemporaryDirectory() as ws_dir:
            roles_f = os.path.join(ws_dir, "cleanroom_roles.toml")
            with open(roles_f, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.lib]\nname = "lib"\nsrc_pattern = "{unit_dir}/lib/{unit_name}.py"\n\n'
                    '[roles.test]\nname = "test"\nsrc_pattern = "{unit_dir}/tests/{unit_name}_test.py"\n'
                )

            target_f = os.path.join(ws_dir, "lib", "foo.py")
            os.makedirs(os.path.dirname(target_f), exist_ok=True)
            with open(target_f, "w", encoding="utf-8") as f:
                f.write("# foo\n")

            old_cwd = os.getcwd()
            try:
                os.chdir(ws_dir)
                with open(".cleanroom_role.json", "w", encoding="utf-8") as f:
                    f.write('{"role_name": "test", "dir_scope": "scope"}')

                code_blame = self.handler.run_blame("lib/foo.py", "valid critique", repo_root=ws_dir)
                self.assertEqual(code_blame, 0)

                buf_p = os.path.join(ws_dir, ".cleanroom_blame_buffer.json")
                self.assertTrue(os.path.isfile(buf_p))

                checker = self.scope.get_singleton(check_impl.WorkspaceChecker)
                checker.record_check_executed(ws_dir, target_f, passed=False)

                code_fail = self.handler.run_fail(file_path="lib/foo.py", reason="stuck at impasse", repo_root=ws_dir)
                self.assertEqual(code_fail, 0)
            finally:
                os.chdir(old_cwd)



# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspaceCommandHandlerFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspaceCommandHandler."""

    @settings(max_examples=30)
    @given(
        target=st.text(min_size=1, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz_"),
        exit_code=st.sampled_from([0, 1, 2]),
    )
    def test_submit_verification_exit_code_invariants(self, target: str, exit_code: int) -> None:
        state = CommandHandlerState(check_files_exit_code=exit_code)
        fake = make_command_handler_fake(state)

        res = fake.run_submit(f"lib/{target}.py", "Summary")
        self.assertEqual(res, exit_code)
        if exit_code == 0:
            self.assertIn(f"lib/{target}.py", state.submitted_targets)
        else:
            self.assertNotIn(f"lib/{target}.py", state.submitted_targets)
