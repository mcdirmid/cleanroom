"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceStubSynthesizer."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import stat
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense.collections import PretenseDict, PretenseSet
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.workspace.lib import role_registry
from update_with_ai.parts.workspace.lib.stub import WorkspaceStubSynthesizer


@dataclass
class StubSynthesizerState:
    """Canonical model state for WorkspaceStubSynthesizer."""
    valid_stubs: PretenseSet[str] = field(default_factory=PretenseSet)
    stub_dep_files: PretenseSet[str] = field(default_factory=PretenseSet)
    generated_count: int = 0


proto = StateMachineProto[StubSynthesizerState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_stub_data(): pass

@seed_stub_data.arguments
def _(
    state: StubSynthesizerState,
    this: Any,
    valid_stubs: Optional[Sequence[str]] | NotBoundType = NotBound,
    stub_dep_files: Optional[Sequence[str]] | NotBoundType = NotBound,
) -> Optional[Tuple[Sequence[str], Sequence[str]]]:
    vs = ("lib/sample.py",) if isinstance(valid_stubs, NotBoundType) or valid_stubs is None else tuple(valid_stubs)
    sf = ("lib/sample.py",) if isinstance(stub_dep_files, NotBoundType) or stub_dep_files is None else tuple(stub_dep_files)
    return (vs, sf)

@seed_stub_data.provide
def _(
    state: StubSynthesizerState,
    this: Any,
    valid_stubs: Sequence[str],
    stub_dep_files: Sequence[str],
    result: None = None,
) -> None:
    state.valid_stubs.update(valid_stubs)
    state.stub_dep_files.update(stub_dep_files)


# ==============================================================================
# 2. Stub Transitions
# ==============================================================================

@proto.transition(WorkspaceStubSynthesizer.is_valid_test_stub)
def is_valid_test_stub(): pass

@is_valid_test_stub.arguments
def _(
    state: StubSynthesizerState,
    this: Any,
    file_path: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    f = "lib/sample.py" if isinstance(file_path, NotBoundType) else str(file_path)
    return (f,)

@is_valid_test_stub.returns
def _(
    state: StubSynthesizerState,
    this: Any,
    file_path: str,
    outcome: object = NotBound,
) -> Optional[Outcome[bool]]:
    expected = file_path in state.valid_stubs
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(WorkspaceStubSynthesizer.is_stub_dep_file)
def is_stub_dep_file(): pass

@is_stub_dep_file.arguments
def _(
    state: StubSynthesizerState,
    this: Any,
    rel_path: str | NotBoundType = NotBound,
    role_def: role_registry.RoleDefinition | NotBoundType = NotBound,
    repo_root: Optional[str] | NotBoundType = NotBound,
) -> Optional[Tuple[str, role_registry.RoleDefinition, Optional[str]]]:
    rp = "lib/sample.py" if isinstance(rel_path, NotBoundType) else str(rel_path)
    rd = (
        role_registry.RoleDefinition(
            role_name="test",
            guide_path="guides/test.md",
            writable_file_patterns=("tests/*.py",),
            readonly_file_patterns=(),
            feedback_role_deps=(),
            stub_role_deps=("lib",),
        )
        if isinstance(role_def, NotBoundType)
        else role_def
    )
    rr = None if isinstance(repo_root, NotBoundType) else repo_root
    return (rp, rd, rr)

@is_stub_dep_file.returns
def _(
    state: StubSynthesizerState,
    this: Any,
    rel_path: str,
    role_def: role_registry.RoleDefinition,
    repo_root: Optional[str],
    outcome: object = NotBound,
) -> Optional[Outcome[bool]]:
    expected = rel_path in state.stub_dep_files
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(WorkspaceStubSynthesizer.generate_readonly_test_stub)
def generate_readonly_test_stub(): pass

@generate_readonly_test_stub.arguments
def _(
    state: StubSynthesizerState,
    this: Any,
    pyi_path: Optional[str] | NotBoundType = NotBound,
    stem: str | NotBoundType = NotBound,
    out_path: str | NotBoundType = NotBound,
    dep_dir: str | NotBoundType = NotBound,
    part_map: Optional[Dict[str, Tuple[str, str]]] | NotBoundType = NotBound,
) -> Optional[Tuple[Optional[str], str, str, str, Optional[Dict[str, Tuple[str, str]]]]]:
    pyi = None if isinstance(pyi_path, NotBoundType) else pyi_path
    st = "sample" if isinstance(stem, NotBoundType) else str(stem)
    out = "/tmp/sample.py" if isinstance(out_path, NotBoundType) else str(out_path)
    dep = "" if isinstance(dep_dir, NotBoundType) else str(dep_dir)
    pm = None if isinstance(part_map, NotBoundType) else part_map
    return (pyi, st, out, dep, pm)

@generate_readonly_test_stub.returns
def _(
    state: StubSynthesizerState,
    this: Any,
    pyi_path: Optional[str],
    stem: str,
    out_path: str,
    dep_dir: str,
    part_map: Optional[Dict[str, Tuple[str, str]]],
    outcome: object = NotBound,
) -> Optional[Outcome[None]]:
    state.generated_count += 1
    state.valid_stubs.add(out_path)
    return Value(None)


@proto.transition(WorkspaceStubSynthesizer.sync_all_stub_deps)
def sync_all_stub_deps(): pass

@sync_all_stub_deps.arguments
def _(
    state: StubSynthesizerState,
    this: Any,
    workspace_dir: str | NotBoundType = NotBound,
    main_root: str | NotBoundType = NotBound,
    role_def: role_registry.RoleDefinition | NotBoundType = NotBound,
    dir_scope: str | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, role_registry.RoleDefinition, str]]:
    ws = "/tmp/ws" if isinstance(workspace_dir, NotBoundType) else str(workspace_dir)
    mr = "/tmp/repo" if isinstance(main_root, NotBoundType) else str(main_root)
    rd = (
        role_registry.RoleDefinition(
            role_name="test",
            guide_path="guides/test.md",
            writable_file_patterns=("tests/*.py",),
            readonly_file_patterns=(),
            feedback_role_deps=(),
            stub_role_deps=("lib",),
        )
        if isinstance(role_def, NotBoundType)
        else role_def
    )
    ds = "staging" if isinstance(dir_scope, NotBoundType) else str(dir_scope)
    return (ws, mr, rd, ds)

@sync_all_stub_deps.returns
def _(
    state: StubSynthesizerState,
    this: Any,
    workspace_dir: str,
    main_root: str,
    role_def: role_registry.RoleDefinition,
    dir_scope: str,
    outcome: object = NotBound,
) -> Optional[Outcome[int]]:
    expected = len(state.stub_dep_files)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_stub_fake(state: Optional[StubSynthesizerState] = None) -> WorkspaceStubSynthesizer:
    """Instantiate a synthesized WorkspaceStubSynthesizer fake."""
    st = state or StubSynthesizerState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(WorkspaceStubSynthesizer)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestWorkspaceStubSynthesizerUnit(unittest.TestCase):
    """Unit tests for synthesized WorkspaceStubSynthesizer fake."""

    def setUp(self) -> None:
        self.state = StubSynthesizerState()
        self.sm = proto.make_state_machine(self.state)
        self.sm.seed_stub_data(
            valid_stubs=["lib/calc.py"],
            stub_dep_files=["lib/calc.py"],
        )
        self.fake: WorkspaceStubSynthesizer = self.sm.as_fake(WorkspaceStubSynthesizer)

    def test_is_valid_test_stub(self) -> None:
        self.assertTrue(self.fake.is_valid_test_stub("lib/calc.py"))
        self.assertFalse(self.fake.is_valid_test_stub("other/file.py"))

    def test_is_stub_dep_file(self) -> None:
        rd = role_registry.RoleDefinition(
            role_name="test",
            guide_path="guides/test.md",
            writable_file_patterns=("tests/*.py",),
            readonly_file_patterns=(),
            feedback_role_deps=(),
            stub_role_deps=("lib",),
        )
        self.assertTrue(self.fake.is_stub_dep_file("lib/calc.py", rd))
        self.assertFalse(self.fake.is_stub_dep_file("other/calc.py", rd))


class TestWorkspaceStubSynthesizerImplReal(unittest.TestCase):
    """Direct unit tests for stub_impl.py."""

    def setUp(self) -> None:
        from support.lib.lifecycle import LifecycleRegistry, enter_phase
        from update_with_ai.parts.agent.lib import session as agent_session
        from update_with_ai.parts.workspace.lib import role_registry_impl, roles_impl, stub, stub_impl

        self.registry = LifecycleRegistry()
        roles_impl.__initialize__(self.registry)
        role_registry_impl.__initialize__(self.registry)
        stub_impl.__initialize__(self.registry)
        self.phase_cm = enter_phase(agent_session.agent_session, registry=self.registry)
        self.scope = self.phase_cm.__enter__()
        self.stub_synth = self.scope.get_singleton(stub_impl.WorkspaceStubSynthesizer)

    def tearDown(self) -> None:
        self.phase_cm.__exit__(None, None, None)

    def test_generate_readonly_test_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pyi_path = os.path.join(tmp_dir, "calc.pyi")
            with open(pyi_path, "w", encoding="utf-8") as f:
                f.write(
                    "class Calculator:\n"
                    "    def add(self, a: int, b: int) -> int: ...\n"
                    "def standalone() -> str: ...\n"
                )
            out_stub = os.path.join(tmp_dir, "calc.py")
            self.stub_synth.generate_readonly_test_stub(pyi_path, "calc", out_stub)

            self.assertTrue(os.path.isfile(out_stub))
            self.assertTrue(self.stub_synth.is_valid_test_stub(out_stub))

            with open(out_stub, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("class Calculator:", content)
            self.assertIn("def add", content)
            self.assertIn("def standalone", content)
            self.assertIn("raise NotImplementedError", content)

    def test_sync_all_stub_deps_and_is_stub_dep_file(self) -> None:
        with tempfile.TemporaryDirectory() as base_tmp:
            repo_root = os.path.join(base_tmp, "repo")
            ws_dir = os.path.join(base_tmp, "ws")
            os.makedirs(repo_root, exist_ok=True)
            os.makedirs(ws_dir, exist_ok=True)

            roles_file = os.path.join(repo_root, "cleanroom_roles.toml")
            with open(roles_file, "w", encoding="utf-8") as f:
                f.write(
                    '[roles.low]\n'
                    'name = "low"\n'
                    'src_pattern = "{unit_dir}/low/{unit_name}.pyi"\n\n'
                    '[roles.lib]\n'
                    'name = "lib"\n'
                    'src_pattern = "{unit_dir}/lib/{unit_name}.py"\n'
                    'role_deps = ["low"]\n\n'
                    '[roles.test]\n'
                    'name = "test"\n'
                    'src_pattern = "{unit_dir}/tests/{unit_name}_test.py"\n'
                    'role_deps = ["low"]\n'
                    'stub_role_deps = ["lib"]\n'
                )

            # Create parts/unit/low/sample.pyi in repo
            scope_dir = os.path.join(repo_root, "scope", "parts", "unit")
            os.makedirs(os.path.join(scope_dir, "low"), exist_ok=True)
            with open(os.path.join(scope_dir, "low", "sample.pyi"), "w", encoding="utf-8") as f:
                f.write("def foo() -> int: ...\n")

            from update_with_ai.parts.workspace.lib import roles_impl
            resolver = self.scope.get_singleton(roles_impl.RoleResolver)
            test_role = resolver.resolve_role_definition("test", repo_root=repo_root)

            # Check is_stub_dep_file
            self.assertTrue(self.stub_synth.is_stub_dep_file("parts/unit/lib/sample.py", test_role, repo_root))
            self.assertFalse(self.stub_synth.is_stub_dep_file("parts/unit/tests/sample_test.py", test_role, repo_root))

            # Sync all stub deps
            count = self.stub_synth.sync_all_stub_deps(
                workspace_dir=ws_dir,
                main_root=repo_root,
                role_def=test_role,
                dir_scope="scope",
            )
            self.assertEqual(count, 1)

            ws_stub = os.path.join(ws_dir, "scope", "parts", "unit", "lib", "sample.py")
            self.assertTrue(os.path.isfile(ws_stub))
            self.assertTrue(self.stub_synth.is_valid_test_stub(ws_stub))


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestWorkspaceStubSynthesizerFuzz(unittest.TestCase):
    """Property fuzz testing for WorkspaceStubSynthesizer."""

    @settings(max_examples=30)
    @given(
        stubs=st.lists(
            st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    def test_stub_invariants(self, stubs: list[str]) -> None:
        state = StubSynthesizerState()
        sm = proto.make_state_machine(state)
        sm.seed_stub_data(valid_stubs=stubs, stub_dep_files=stubs)
        fake = sm.as_fake(WorkspaceStubSynthesizer)

        for s in stubs:
            self.assertTrue(fake.is_valid_test_stub(s))
