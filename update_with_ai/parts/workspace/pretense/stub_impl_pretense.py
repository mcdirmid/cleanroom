"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for WorkspaceStubSynthesizer."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import stat
import tempfile
from typing import Any, Dict, List, Optional, Sequence, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict, PretenseSet
from update_with_ai.parts.workspace.lib import role_registry
from update_with_ai.parts.workspace.lib.stub import WorkspaceStubSynthesizer


@dataclass
class StubSynthesizerState:
    """Canonical model state for WorkspaceStubSynthesizer."""
    valid_stubs: PretenseSet[str] = field(default_factory=PretenseSet)
    stub_dep_files: PretenseSet[str] = field(default_factory=PretenseSet)
    generated_count: int = 0


class WorkspaceStubStateMachine(StateMachine[StubSynthesizerState]):
    """Unified Pretense State Machine for WorkspaceStubSynthesizer."""

    def __init__(
        self,
        state: Optional[StubSynthesizerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or StubSynthesizerState(), singletons=singletons)

    @transition.seeding(name="seed_stub_data")
    def seed_stub_data(
        self,
        ctx: TransitionContext[Any, [Optional[Sequence[str]], Optional[Sequence[str]]], None],
    ) -> None:
        ctx.arguments(
                    valid_stubs=Domain(strategy=lambda: ('lib/sample.py',)),
                    stub_dep_files=Domain(strategy=lambda: ('lib/sample.py',)),
                )
        ctx.returns(lambda valid_stubs=None, stub_dep_files=None: None)
        ctx.update(lambda res, valid_stubs=None, stub_dep_files=None: (
            self.state.valid_stubs.update(valid_stubs or ()),
            self.state.stub_dep_files.update(stub_dep_files or ()),
        ))

    @transition(WorkspaceStubSynthesizer.is_valid_test_stub)
    def is_valid_test_stub(
        self,
        ctx: TransitionContext[WorkspaceStubSynthesizer, [str], bool],
    ) -> None:
        ctx.arguments(file_path=Domain(strategy=lambda: 'lib/sample.py'))
        ctx.returns(lambda file_path="lib/sample.py": file_path in self.state.valid_stubs)
        ctx.update(lambda res, file_path="lib/sample.py": None)

    @transition(WorkspaceStubSynthesizer.is_stub_dep_file)
    def is_stub_dep_file(
        self,
        ctx: TransitionContext[WorkspaceStubSynthesizer, [str, role_registry.RoleDefinition, Optional[str]], bool],
    ) -> None:
        ctx.arguments(
                    rel_path=Domain(strategy=lambda: 'lib/sample.py'),
                    role_def=Domain(strategy=lambda: role_registry.RoleDefinition(role_name='test', guide_path='guides/test.md', writable_file_patterns=('tests/*.py',), readonly_file_patterns=(), feedback_role_deps=(), stub_role_deps=('lib',))),
                    repo_root=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda rel_path="lib/sample.py", role_def=None, repo_root=None: rel_path in self.state.stub_dep_files)
        ctx.update(lambda res, rel_path="lib/sample.py", role_def=None, repo_root=None: None)

    @transition(WorkspaceStubSynthesizer.generate_readonly_test_stub)
    def generate_readonly_test_stub(
        self,
        ctx: TransitionContext[WorkspaceStubSynthesizer, [Optional[str], str, str, str, Optional[Dict[str, Tuple[str, str]]]], None],
    ) -> None:
        ctx.arguments(
                    pyi_path=Domain(strategy=lambda: None),
                    stem=Domain(strategy=lambda: 'sample'),
                    out_path=Domain(strategy=lambda: '/tmp/sample.py'),
                    dep_dir=Domain(strategy=lambda: ''),
                    part_map=Domain(strategy=lambda: None),
                )
        ctx.returns(lambda pyi_path=None, stem="sample", out_path="/tmp/sample.py", dep_dir="", part_map=None: None)
        ctx.update(lambda res, pyi_path=None, stem="sample", out_path="/tmp/sample.py", dep_dir="", part_map=None: (
            setattr(self.state, "generated_count", self.state.generated_count + 1),
            self.state.valid_stubs.add(out_path),
        ))

    @transition(WorkspaceStubSynthesizer.sync_all_stub_deps)
    def sync_all_stub_deps(
        self,
        ctx: TransitionContext[WorkspaceStubSynthesizer, [str, str, role_registry.RoleDefinition, str], int],
    ) -> None:
        ctx.arguments(
                    workspace_dir=Domain(strategy=lambda: '/tmp/ws'),
                    main_root=Domain(strategy=lambda: '/tmp/repo'),
                    role_def=Domain(strategy=lambda: role_registry.RoleDefinition(role_name='test', guide_path='guides/test.md', writable_file_patterns=('tests/*.py',), readonly_file_patterns=(), feedback_role_deps=(), stub_role_deps=('lib',))),
                    dir_scope=Domain(strategy=lambda: 'staging'),
                )
        ctx.returns(lambda workspace_dir="/tmp/ws", main_root="/tmp/repo", role_def=None, dir_scope="staging": len(self.state.stub_dep_files))
        ctx.update(lambda res, workspace_dir="/tmp/ws", main_root="/tmp/repo", role_def=None, dir_scope="staging": None)


proto = WorkspaceStubStateMachine()


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
