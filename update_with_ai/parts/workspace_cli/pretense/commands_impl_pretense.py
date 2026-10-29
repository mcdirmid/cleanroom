"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceCommandHandler."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Dict, List, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict, PretenseSet
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


class WorkspaceCommandStateMachine(StateMachine[CommandHandlerState]):
    """Unified Pretense State Machine for WorkspaceCommandHandler."""

    def __init__(
        self,
        state: Optional[CommandHandlerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or CommandHandlerState(), singletons=singletons)

    @transition.seeding(name="seed_command_state")
    def seed_command_state(
        self,
        ctx: TransitionContext[Any, [int], None],
    ) -> None:
        ctx.arguments(check_files_exit_code=Domain(strategy=lambda: 0))
        ctx.returns(lambda check_files_exit_code=0: None)
        ctx.update(lambda res, check_files_exit_code=0: setattr(self.state, "check_files_exit_code", int(check_files_exit_code)))

    @transition(WorkspaceCommandHandler.run_get_work)
    def run_get_work(
        self,
        ctx: TransitionContext[WorkspaceCommandHandler, [Optional[str], Optional[str], bool, Optional[int]], int],
    ) -> None:
        ctx.arguments(
                    dir_scope=Domain(strategy=lambda: None),
                    repo_root=Domain(strategy=lambda: None),
                    force=Domain(strategy=lambda: False),
                    batch_size=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda dir_scope=None, repo_root=None, force=False, batch_size=None: 0)
        ctx.update(lambda res, dir_scope=None, repo_root=None, force=False, batch_size=None: None)

    @transition(WorkspaceCommandHandler.run_check_files)
    def run_check_files(
        self,
        ctx: TransitionContext[WorkspaceCommandHandler, [Optional[str], Optional[str]], int],
    ) -> None:
        ctx.arguments(
                    target=Domain(strategy=lambda: None),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda target=None, repo_root=None: self.state.check_files_exit_code)
        ctx.update(lambda res, target=None, repo_root=None: None)

    @transition(WorkspaceCommandHandler.run_submit)
    def run_submit(
        self,
        ctx: TransitionContext[WorkspaceCommandHandler, [str, Optional[str], Optional[str], bool], int],
    ) -> None:
        ctx.arguments(
                    target=Domain(strategy=lambda: 'lib/module.py'),
                    summary=Domain(strategy=lambda: 'Implemented'),
                    repo_root=Domain(strategy=lambda: None),
                    no_verify=Domain(strategy=lambda: False),
                )
        ctx.returns(lambda target="lib/module.py", summary="Implemented", repo_root=None, no_verify=False: (
            0 if no_verify else self.state.check_files_exit_code
        ))
        def provide(res: int, target: str = "lib/module.py", summary: Optional[str] = "Implemented", repo_root: Optional[str] = None, no_verify: bool = False) -> None:
            if res == 0:
                self.state.submitted_targets.add(target)
        ctx.update(provide)

    @transition(WorkspaceCommandHandler.run_blame)
    def run_blame(
        self,
        ctx: TransitionContext[WorkspaceCommandHandler, [str, str, Optional[str]], int],
    ) -> None:
        ctx.arguments(
                    culprit_file=Domain(strategy=lambda: 'lib/culprit.py'),
                    critique=Domain(strategy=lambda: 'Missing error check'),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda culprit_file="lib/culprit.py", critique="Missing error check", repo_root=None: (
            0 if "\n" not in critique else 1
        ))
        def provide(res: int, culprit_file: str = "lib/culprit.py", critique: str = "Missing error check", repo_root: Optional[str] = None) -> None:
            if res == 0:
                self.state.blamed_files[culprit_file] = critique
        ctx.update(provide)

    @transition(WorkspaceCommandHandler.run_fail)
    def run_fail(
        self,
        ctx: TransitionContext[WorkspaceCommandHandler, [str, Optional[str], Optional[str]], int],
    ) -> None:
        ctx.arguments(
                    file_path=Domain(strategy=lambda: 'lib/module.py'),
                    reason=Domain(strategy=lambda: 'Verification failed'),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda file_path="lib/module.py", reason="Verification failed", repo_root=None: 0)
        def provide(res: int, file_path: str = "lib/module.py", reason: Optional[str] = "Verification failed", repo_root: Optional[str] = None) -> None:
            if reason:
                self.state.failed_files[file_path] = reason
        ctx.update(provide)


proto = WorkspaceCommandStateMachine()


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
