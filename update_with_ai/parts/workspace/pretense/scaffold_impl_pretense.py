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

from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.workspace.lib import roles
from update_with_ai.parts.workspace.lib.scaffold import WorkspaceScaffolder


@dataclass
class ScaffolderState:
    """Canonical model state for WorkspaceScaffolder."""
    written_files: PretenseDict[str, str] = field(default_factory=PretenseDict)
    runner_tools: PretenseSet[str] = field(default_factory=PretenseSet)
    skeletons: PretenseSet[str] = field(default_factory=PretenseSet)


proto = StateMachineProto[ScaffolderState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_scaffolder_data(): pass

@seed_scaffolder_data.arguments
def _(
    state: ScaffolderState,
    this: Any,
    runner_tools: Optional[Sequence[str]] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[str]]]:
    rt = ("get_work", "check_files", "submit", "fail") if isinstance(runner_tools, NotBoundType) or runner_tools is None else tuple(runner_tools)
    return (rt,)

@seed_scaffolder_data.provide
def _(
    state: ScaffolderState,
    this: Any,
    runner_tools: Sequence[str],
    result: None = None,
) -> None:
    state.runner_tools.update(runner_tools)


# ==============================================================================
# 2. Scaffolder Transitions
# ==============================================================================

@proto.transition(WorkspaceScaffolder.write_file_with_permissions)
def write_file_with_permissions(): pass

@write_file_with_permissions.arguments
def _(
    state: ScaffolderState,
    this: Any,
    dst: str | NotBoundType = NotBound,
    content: str | NotBoundType = NotBound,
    readonly: bool | NotBoundType = NotBound,
    executable: bool | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, bool, bool]]:
    d = "/tmp/file.txt" if isinstance(dst, NotBoundType) else str(dst)
    c = "hello" if isinstance(content, NotBoundType) else str(content)
    r = False if isinstance(readonly, NotBoundType) else bool(readonly)
    e = False if isinstance(executable, NotBoundType) else bool(executable)
    return (d, c, r, e)

@write_file_with_permissions.returns
def _(
    state: ScaffolderState,
    this: Any,
    dst: str,
    content: str,
    readonly: bool,
    executable: bool,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.written_files[dst] = content
    return Value(None)


@proto.transition(WorkspaceScaffolder.deploy_runner_zipapps)
def deploy_runner_zipapps(): pass

@deploy_runner_zipapps.arguments
def _(
    state: ScaffolderState,
    this: Any,
    bin_dir: str | NotBoundType = NotBound,
    role_def: Optional[roles.RoleDefinition] | NotBoundType = NotBound,
    can_blame: bool | NotBoundType = NotBound,
) -> Optional[Tuple[str, Optional[roles.RoleDefinition], bool]]:
    bd = "/tmp/bin" if isinstance(bin_dir, NotBoundType) else str(bin_dir)
    rd = None if isinstance(role_def, NotBoundType) else role_def
    cb = True if isinstance(can_blame, NotBoundType) else bool(can_blame)
    return (bd, rd, cb)

@deploy_runner_zipapps.returns
def _(
    state: ScaffolderState,
    this: Any,
    bin_dir: str,
    role_def: Optional[roles.RoleDefinition],
    can_blame: bool,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    for tool in ("get_work", "check_files", "submit", "fail"):
        state.runner_tools.add(f"{bin_dir}/{tool}")
    if can_blame:
        state.runner_tools.add(f"{bin_dir}/blame")
        state.runner_tools.add(f"{bin_dir}/feedback")
    return Value(None)


@proto.transition(WorkspaceScaffolder.write_role_metadata)
def write_role_metadata(): pass

@write_role_metadata.arguments
def _(
    state: ScaffolderState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    role_name: str | NotBoundType = NotBound,
    dir_scope: str | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
    model: Optional[str] | NotBoundType = NotBound,
    batch_size: Optional[int] | NotBoundType = NotBound,
    max_feedback_chars: Optional[int] | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, str, Optional[str], Optional[str], Optional[int], Optional[int]]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    rn = "lib" if isinstance(role_name, NotBoundType) else str(role_name)
    ds = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    m = None if isinstance(model, NotBoundType) else model
    bs = None if isinstance(batch_size, NotBoundType) else batch_size
    mf = None if isinstance(max_feedback_chars, NotBoundType) else max_feedback_chars
    return (ws, rn, ds, rr, m, bs, mf)

@write_role_metadata.returns
def _(
    state: ScaffolderState,
    this: Any,
    workspace_dir: str,
    role_name: str,
    dir_scope: str,
    repo_root: Optional[str],
    model: Optional[str],
    batch_size: Optional[int],
    max_feedback_chars: Optional[int],
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    meta_p = f"{workspace_dir}/.cleanroom_role.json"
    state.written_files[meta_p] = f'{{"role_name": "{role_name}"}}'
    return Value(None)


@proto.transition(WorkspaceScaffolder.write_role_agents_guide)
def write_role_agents_guide(): pass

@write_role_agents_guide.arguments
def _(
    state: ScaffolderState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    role_def: roles.RoleDefinition | NotBoundType = NotBound,
    dir_scope: str | NotBoundType = NotBound,
) -> Optional[Tuple[str, roles.RoleDefinition, str]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    rd = (
        roles.RoleDefinition(
            role_name="lib",
            guide_path="guides/lib.md",
            writable_file_patterns=("lib/*.py",),
            readonly_file_patterns=(),
            feedback_role_deps=(),
        )
        if isinstance(role_def, NotBoundType)
        else role_def
    )
    ds = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    return (ws, rd, ds)

@write_role_agents_guide.returns
def _(
    state: ScaffolderState,
    this: Any,
    workspace_dir: str,
    role_def: roles.RoleDefinition,
    dir_scope: str,
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    guide_p = f"{workspace_dir}/AGENTS.md"
    state.written_files[guide_p] = f"# AGENTS for {role_def.role_name}"
    return Value(None)


@proto.transition(WorkspaceScaffolder.create_missing_target_skeletons)
def create_missing_target_skeletons(): pass

@create_missing_target_skeletons.arguments
def _(
    state: ScaffolderState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    repo_root: str | NotBoundType = NotBound,
    dir_scope: str | NotBoundType = NotBound,
    role_def: roles.RoleDefinition | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, str, roles.RoleDefinition]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    rr = "/tmp/repo" if isinstance(repo_root, NotBoundType) else str(repo_root)
    ds = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    rd = (
        roles.RoleDefinition(
            role_name="lib",
            guide_path="guides/lib.md",
            writable_file_patterns=("lib/*.py",),
            readonly_file_patterns=(),
            feedback_role_deps=(),
        )
        if isinstance(role_def, NotBoundType)
        else role_def
    )
    return (ws, rr, ds, rd)

@create_missing_target_skeletons.returns
def _(
    state: ScaffolderState,
    this: Any,
    workspace_dir: str,
    repo_root: str,
    dir_scope: str,
    role_def: roles.RoleDefinition,
    outcome: object = NotBound,
) -> Optional[Outcome[List[str]]]:
    expected = list(state.skeletons)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


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
