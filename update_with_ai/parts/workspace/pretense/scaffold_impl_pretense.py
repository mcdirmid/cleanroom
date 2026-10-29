"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceScaffolder."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import stat
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest
import zipfile

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict, PretenseSet
from update_with_ai.parts.workspace.lib import roles
from update_with_ai.parts.workspace.lib.scaffold import WorkspaceScaffolder


@dataclass
class ScaffolderState:
    """Canonical model state for WorkspaceScaffolder."""
    written_files: PretenseDict[str, str] = field(default_factory=PretenseDict)
    runner_tools: PretenseSet[str] = field(default_factory=PretenseSet)
    skeletons: PretenseSet[str] = field(default_factory=PretenseSet)


class WorkspaceScaffoldStateMachine(StateMachine[ScaffolderState]):
    """Unified Pretense State Machine for WorkspaceScaffolder."""

    def __init__(
        self,
        state: Optional[ScaffolderState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or ScaffolderState(), singletons=singletons)

    @transition.seeding(name="seed_scaffolder_data")
    def seed_scaffolder_data(
        self,
        ctx: TransitionContext[Any, [Optional[Sequence[str]]], None],
    ) -> None:
        ctx.arguments(runner_tools=Domain(strategy=lambda: ('get_work', 'check_files', 'submit', 'fail')))
        ctx.returns(lambda runner_tools=None: None)
        ctx.update(lambda res, runner_tools=None: (
            self.state.runner_tools.update(runner_tools or ("get_work", "check_files", "submit", "fail"))
        ))

    @transition(WorkspaceScaffolder.write_file_with_permissions)
    def write_file_with_permissions(
        self,
        ctx: TransitionContext[WorkspaceScaffolder, [str, str, bool, bool], None],
    ) -> None:
        ctx.arguments(
                    dst=Domain(strategy=lambda: '/tmp/file.txt'),
                    content=Domain(strategy=lambda: 'hello'),
                    readonly=Domain(strategy=lambda: False),
                    executable=Domain(strategy=lambda: False),
                )
        ctx.returns(lambda dst="/tmp/file.txt", content="hello", readonly=False, executable=False: None)
        ctx.update(lambda res, dst="/tmp/file.txt", content="hello", readonly=False, executable=False: (
            self.state.written_files.__setitem__(dst, content)
        ))

    @transition(WorkspaceScaffolder.deploy_runner_zipapps)
    def deploy_runner_zipapps(
        self,
        ctx: TransitionContext[WorkspaceScaffolder, [str, Optional[roles.RoleDefinition], bool], None],
    ) -> None:
        ctx.arguments(
                    bin_dir=Domain(strategy=lambda: '/tmp/bin'),
                    role_def=Domain(strategy=lambda: None),
                    can_blame=Domain(strategy=lambda: True),
                )
        ctx.returns(lambda bin_dir="/tmp/bin", role_def=None, can_blame=True: None)
        def provide(res: None, bin_dir: str = "/tmp/bin", role_def: Optional[roles.RoleDefinition] = None, can_blame: bool = True) -> None:
            for tool in ("get_work", "check_files", "submit", "fail"):
                self.state.runner_tools.add(f"{bin_dir}/{tool}")
            if can_blame:
                self.state.runner_tools.add(f"{bin_dir}/blame")
                self.state.runner_tools.add(f"{bin_dir}/feedback")
        ctx.update(provide)

    @transition(WorkspaceScaffolder.write_role_metadata)
    def write_role_metadata(
        self,
        ctx: TransitionContext[WorkspaceScaffolder, [str, str, str, Optional[str], Optional[str], Optional[int], Optional[int]], None],
    ) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    role_name=Domain(strategy=lambda: 'lib'),
                    dir_scope=Domain(strategy=lambda: 'staging'),
                    repo_root=Domain(strategy=lambda: None),
                    model=Domain(strategy=lambda: None),
                    batch_size=Domain(strategy=lambda: None),
                    max_feedback_chars=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda workspace_dir="/tmp/ws", role_name="lib", dir_scope="staging", repo_root=None, model=None, batch_size=None, max_feedback_chars=None: None)
        ctx.update(lambda res, workspace_dir="/tmp/ws", role_name="lib", dir_scope="staging", repo_root=None, model=None, batch_size=None, max_feedback_chars=None: (
            self.state.written_files.__setitem__(f"{workspace_dir}/.cleanroom_role.json", f'{{"role_name": "{role_name}"}}')
        ))

    @transition(WorkspaceScaffolder.write_role_agents_guide)
    def write_role_agents_guide(
        self,
        ctx: TransitionContext[WorkspaceScaffolder, [str, roles.RoleDefinition, str], None],
    ) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    role_def=Domain(strategy=lambda: roles.RoleDefinition(role_name='lib', guide_path='guides/lib.md', writable_file_patterns=('lib/*.py',), readonly_file_patterns=(), feedback_role_deps=())),
                    dir_scope=Domain(strategy=lambda: 'staging'),
                )
        ctx.returns(lambda workspace_dir="/tmp/ws", role_def=None, dir_scope="staging": None)
        ctx.update(lambda res, workspace_dir="/tmp/ws", role_def=None, dir_scope="staging": (
            self.state.written_files.__setitem__(f"{workspace_dir}/AGENTS.md", f"# AGENTS for {role_def.role_name if role_def else 'lib'}")
        ))

    @transition(WorkspaceScaffolder.create_missing_target_skeletons)
    def create_missing_target_skeletons(
        self,
        ctx: TransitionContext[WorkspaceScaffolder, [str, str, str, roles.RoleDefinition], List[str]],
    ) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    repo_root=Domain(strategy=lambda: '/tmp/repo'),
                    dir_scope=Domain(strategy=lambda: 'staging'),
                    role_def=Domain(strategy=lambda: roles.RoleDefinition(role_name='lib', guide_path='guides/lib.md', writable_file_patterns=('lib/*.py',), readonly_file_patterns=(), feedback_role_deps=())),
                )
        ctx.returns(lambda workspace_dir="/tmp/ws", repo_root="/tmp/repo", dir_scope="staging", role_def=None: list(self.state.skeletons))
        ctx.update(lambda res, workspace_dir="/tmp/ws", repo_root="/tmp/repo", dir_scope="staging", role_def=None: None)


proto = WorkspaceScaffoldStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_scaffold_fake(state: Optional[ScaffolderState] = None) -> WorkspaceScaffolder:
    """Instantiate a synthesized WorkspaceScaffolder fake."""
    st = state or ScaffolderState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspaceScaffolder)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspaceScaffolderUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspaceScaffolder fake."""

    def setUp(self) -> None:
        self.state = ScaffolderState()
        self.sm = proto.make_state_machine(self.state)
        self.fake: WorkspaceScaffolder = self.sm.as_fake(WorkspaceScaffolder)

    def test_write_file_with_permissions(self) -> None:
        self.fake.write_file_with_permissions("/tmp/test.txt", "content", readonly=False)
        self.assertEqual(self.state.written_files["/tmp/test.txt"], "content")

    def test_deploy_runner_zipapps(self) -> None:
        self.fake.deploy_runner_zipapps("/tmp/bin")
        self.assertIn("/tmp/bin/get_work", self.state.runner_tools)


class TestWorkspaceScaffolderImplReal(unittest.TestCase):
    """Direct unit tests for scaffold_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.workspace.lib import role_registry_impl, roles_impl, scaffold, scaffold_impl

        self.registry = LifecycleRegistry()
        roles_impl.__initialize__(self.registry)
        role_registry_impl.__initialize__(self.registry)
        scaffold_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.scaffolder = self.scope.get_singleton(scaffold_impl.WorkspaceScaffolder)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_write_file_with_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Writable file
            w_file = os.path.join(tmp_dir, "writable.txt")
            self.scaffolder.write_file_with_permissions(w_file, "write content", readonly=False)
            self.assertTrue(os.path.isfile(w_file))
            mode = stat.S_IMODE(os.stat(w_file).st_mode)
            self.assertEqual(mode, 0o644)

            # Read-only file
            ro_file = os.path.join(tmp_dir, "readonly.txt")
            self.scaffolder.write_file_with_permissions(ro_file, "ro content", readonly=True)
            self.assertTrue(os.path.isfile(ro_file))
            mode = stat.S_IMODE(os.stat(ro_file).st_mode)
            self.assertEqual(mode, 0o444)

            # Overwrite read-only file
            self.scaffolder.write_file_with_permissions(ro_file, "new content", readonly=False)
            with open(ro_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "new content")

            # Executable file
            exe_file = os.path.join(tmp_dir, "exec.sh")
            self.scaffolder.write_file_with_permissions(exe_file, "#!/bin/sh\n", executable=True)
            mode = stat.S_IMODE(os.stat(exe_file).st_mode)
            self.assertEqual(mode, 0o755)

    def test_deploy_runner_zipapps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bin_dir = os.path.join(tmp_dir, "bin")
            os.makedirs(bin_dir, exist_ok=True)
            stale_cov = os.path.join(bin_dir, "coverage")
            with open(stale_cov, "w") as f:
                f.write("stale")

            self.scaffolder.deploy_runner_zipapps(bin_dir)
            self.assertFalse(os.path.exists(stale_cov))

            for tool in ("get_work", "check_files", "submit", "blame", "feedback", "fail"):
                tool_path = os.path.join(bin_dir, tool)
                self.assertTrue(os.path.isfile(tool_path), f"Missing {tool}")
                mode = stat.S_IMODE(os.stat(tool_path).st_mode)
                self.assertEqual(mode, 0o755)

            # Omit blame capability
            role_no_blame = roles.RoleDefinition(
                role_name="lib",
                guide_path="guides/lib.md",
                writable_file_patterns=["lib/*.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=[],
            )
            self.scaffolder.deploy_runner_zipapps(bin_dir, role_def=role_no_blame)
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "blame")))
            self.assertFalse(os.path.exists(os.path.join(bin_dir, "feedback")))

    def test_write_role_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.scaffolder.write_role_metadata(
                tmp_dir,
                role_name="lib",
                dir_scope="parts/example",
                model="gpt-4o",
                batch_size=3,
                max_feedback_chars=2000,
            )
            meta_path = os.path.join(tmp_dir, ".cleanroom_role.json")
            self.assertTrue(os.path.isfile(meta_path))
            mode = stat.S_IMODE(os.stat(meta_path).st_mode)
            self.assertEqual(mode, 0o644)

            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["role"], "lib")
            self.assertEqual(data["role_name"], "lib")
            self.assertEqual(data["dir_scope"], "parts/example")
            self.assertEqual(data["model"], "gpt-4o")

    def test_write_role_agents_guide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            role_def = roles.RoleDefinition(
                role_name="lib",
                guide_path="guides/lib.md",
                writable_file_patterns=["lib/*.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=[],
            )
            self.scaffolder.write_role_agents_guide(tmp_dir, role_def, "parts/sample")
            agents_md = os.path.join(tmp_dir, "AGENTS.md")
            self.assertTrue(os.path.isfile(agents_md))
            with open(agents_md, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Cleanroom Role Instructions: Lib", content)
            self.assertIn("bin/check_files", content)
            self.assertIn("bin/submit", content)

    def test_create_missing_target_skeletons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ws_dir = os.path.join(tmp_dir, "ws")
            repo_root = os.path.join(tmp_dir, "repo")
            os.makedirs(ws_dir, exist_ok=True)
            os.makedirs(repo_root, exist_ok=True)

            role_def = roles.RoleDefinition(
                role_name="lib",
                guide_path="guides/lib.md",
                writable_file_patterns=["lib/*.py"],
                readonly_file_patterns=["low/*.pyi"],
                feedback_role_deps=[],
                src_pattern="{unit_dir}/lib/{unit_name}.py",
                template="# generated template\n",
            )
            created = self.scaffolder.create_missing_target_skeletons(
                ws_dir, repo_root, "scope", role_def
            )
            self.assertIsInstance(created, list)


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspaceScaffolderFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspaceScaffolder."""

    @settings(max_examples=30)
    @given(
        tools=st.lists(
            st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    def test_scaffolder_invariants(self, tools: list[str]) -> None:
        state = ScaffolderState()
        sm = proto.make_state_machine(state)
        sm.seed_scaffolder_data(runner_tools=tools)
        fake = sm.as_fake(WorkspaceScaffolder)

        fake.deploy_runner_zipapps("/tmp/bin", can_blame=True)
        self.assertIn("/tmp/bin/submit", state.runner_tools)
