"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for AliasManager."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

from pretense import Domain, StateMachine, TransitionContext, transition
from pretense.collections import PretenseDict
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Value
from update_with_ai.parts.agent.lib.file_alias import (
    AliasManager,
    BoundFile,
    FileAlias,
    ReadOnlyFile,
    ReadWriteFile,
    RelativePath,
    SanitizedText,
    UnboundFile,
    UnsanitizedText,
)
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress


@dataclass
class AliasManagerState:
    """Canonical model state for AliasManager."""
    workspace_root: str = "/workspace"
    bound_files: PretenseDict[str, BoundFile] = field(default_factory=PretenseDict)
    unbound_files: PretenseDict[str, UnboundFile] = field(default_factory=PretenseDict)


class AliasManagerStateMachine(StateMachine[AliasManagerState]):
    """Pretense StateMachine for AliasManager."""

    def __init__(self, state: Optional[AliasManagerState] = None):
        super().__init__(state=state or AliasManagerState())

    # ==============================================================================
    # 1. Seeding Transitions
    # ==============================================================================

    @transition.seeding()
    def seed_workspace_root(
        self,
        ctx: TransitionContext[None, [str], None],
    ) -> None:
        ctx.arguments(workspace_root=Domain(strategy=lambda: '/workspace'))
        ctx.update(
            lambda res, workspace_root="/workspace": setattr(self.state, "workspace_root", str(workspace_root))
        )

    @transition.seeding()
    def seed_bound_file(
        self,
        ctx: TransitionContext[
            None,
            [str, Optional[str], Optional[str], Optional[str], bool],
            None,
        ],
    ) -> None:
        ctx.arguments(
                    relative_path=Domain(strategy=lambda: 'lib/module.py'),
                    workspace_path=Domain(strategy=lambda: 'src/lib/module.py'),
                    owning_unit=Domain(strategy=lambda: 'target'),
                    owning_role=Domain(strategy=lambda: 'lib'),
                    is_readonly=Domain(strategy=lambda: False),
                )
        def _consequent(
            res: None,
            relative_path: str = "lib/module.py",
            workspace_path: Optional[str] = None,
            owning_unit: Optional[str] = None,
            owning_role: Optional[str] = None,
            is_readonly: bool = False,
        ) -> None:
            rel = relative_path
            ws = f"src/{rel}" if workspace_path is None else str(workspace_path)
            unit = "target" if owning_unit is None else str(owning_unit)
            role = "lib" if owning_role is None else str(owning_role)
            cls = ReadOnlyFile if is_readonly else ReadWriteFile
            bf = cls(
                relative_path=RelativePath(rel),
                workspace_path=file_paths.WorkspacePath(file_paths.PathString(ws)),
                owning_node=DagNode(UnitAddress(unit), RoleAddress(role)),
            )
            self.state.bound_files[rel] = bf

        ctx.update(_consequent)

    # ==============================================================================
    # 2. Interface Transitions
    # ==============================================================================

    @transition(name="workspace_root")
    def workspace_root(
        self,
        ctx: TransitionContext[AliasManager, [], file_paths.WorkspaceRoot],
    ) -> None:
        ctx.returns(lambda: file_paths.WorkspaceRoot(file_paths.PathString(self.state.workspace_root)))

    @transition(AliasManager.to_alias)
    def to_alias(
        self,
        ctx: TransitionContext[AliasManager, [str], FileAlias],
    ) -> None:
        ctx.arguments(path=Domain(strategy=lambda: next(iter(self.state.bound_files.keys())) if self.state.bound_files else 'demo.py'))
        def _returns(path: str = "demo.py") -> FileAlias:
            p_str = str(path)
            if p_str in self.state.bound_files:
                return self.state.bound_files[p_str]
            if p_str in self.state.unbound_files:
                return self.state.unbound_files[p_str]
            base = os.path.basename(p_str)
            basename_matches = [bf for bf in self.state.bound_files.values() if os.path.basename(bf.relative_path) == base]
            if len(basename_matches) == 1:
                return basename_matches[0]
            return UnboundFile(relative_path=RelativePath(p_str))
        ctx.returns(_returns)

    @transition(AliasManager.sanitize_text)
    def sanitize_text(
        self,
        ctx: TransitionContext[AliasManager, [str], SanitizedText],
    ) -> None:
        ctx.arguments(text=Domain(strategy=lambda: UnsanitizedText('Hello /workspace/src/lib/module.py')))
        def _returns(text: str = "") -> SanitizedText:
            res = str(text)
            root = self.state.workspace_root.rstrip("/")
            for rel_path, bf in sorted(self.state.bound_files.items(), key=lambda item: len(item[1].workspace_path.path), reverse=True):
                ws_norm = os.path.normpath(bf.workspace_path.path)
                abs_p = os.path.normpath(f"{root}/{ws_norm}")
                if abs_p in res:
                    res = res.replace(abs_p, rel_path)
                if ws_norm in res:
                    res = res.replace(ws_norm, rel_path)
            if root and root in res:
                res = res.replace(f"{root}/", "").replace(root, "")
            return SanitizedText(res)
        ctx.returns(_returns)


proto = AliasManagerStateMachine()


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_alias_manager_fake(state: Optional[AliasManagerState] = None) -> AliasManager:
    """Instantiate a synthesized AliasManager fake with Pretense."""
    sm = AliasManagerStateMachine(state)
    return sm.as_fake(AliasManager)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestAliasManagerUnit(unittest.TestCase):
    """Unit tests verifying synthesized AliasManager fake."""

    def setUp(self) -> None:
        self.state = AliasManagerState(workspace_root="/home/user/project")
        self.sm = AliasManagerStateMachine(self.state)
        self.sm.seed_bound_file("lib/utils.py", "pkg/lib/utils.py", "pkg", "lib", is_readonly=True)
        self.sm.seed_bound_file("tests/utils_test.py", "pkg/tests/utils_test.py", "pkg", "test", is_readonly=False)
        self.fake: AliasManager = self.sm.as_fake(AliasManager)

    def test_workspace_root(self) -> None:
        self.assertEqual(self.fake.workspace_root.path, "/home/user/project")

    def test_to_alias_bound_files(self) -> None:
        alias1 = self.fake.to_alias("lib/utils.py")
        self.assertIsInstance(alias1, ReadOnlyFile)
        self.assertEqual(alias1.relative_path, "lib/utils.py")
        self.assertEqual(str(alias1), "lib/utils.py")

        alias2 = self.fake.to_alias("tests/utils_test.py")
        self.assertIsInstance(alias2, ReadWriteFile)
        self.assertEqual(alias2.relative_path, "tests/utils_test.py")

    def test_to_alias_basename_lookup(self) -> None:
        alias = self.fake.to_alias("utils.py")
        self.assertIsInstance(alias, ReadOnlyFile)
        self.assertEqual(alias.relative_path, "lib/utils.py")

    def test_to_alias_unbound_file(self) -> None:
        alias = self.fake.to_alias("nonexistent.txt")
        self.assertIsInstance(alias, UnboundFile)
        self.assertEqual(alias.relative_path, "nonexistent.txt")

    def test_sanitize_text(self) -> None:
        raw = UnsanitizedText("Error in /home/user/project/pkg/lib/utils.py at line 42")
        sanitized = self.fake.sanitize_text(raw)
        self.assertEqual(sanitized, "Error in lib/utils.py at line 42")


# ==============================================================================
# 5. Hypothesis Fuzz Testing
# ==============================================================================

class TestAliasManagerFuzz(unittest.TestCase):
    """Property fuzz testing for AliasManager."""

    @settings(max_examples=30)
    @given(
        root=st.from_regex(r"^/[a-z]{3,8}/[a-z]{3,8}$", fullmatch=True),
        file_names=st.lists(
            st.from_regex(r"^[a-z]{3,6}\.py$", fullmatch=True),
            min_size=1,
            max_size=5,
            unique=True,
        ),
    )
    def test_alias_resolution_and_sanitization_invariants(self, root: str, file_names: list[str]) -> None:
        state = AliasManagerState(workspace_root=root)
        sm = AliasManagerStateMachine(state)
        for i, fname in enumerate(file_names):
            sm.seed_bound_file(f"src/{fname}", f"ws/{fname}", f"node_{i}", "role", is_readonly=(i % 2 == 0))

        fake = sm.as_fake(AliasManager)
        self.assertEqual(fake.workspace_root.path, root)

        for i, fname in enumerate(file_names):
            rel = f"src/{fname}"
            alias = fake.to_alias(rel)
            self.assertEqual(alias.relative_path, rel)
            if i % 2 == 0:
                self.assertIsInstance(alias, ReadOnlyFile)
            else:
                self.assertIsInstance(alias, ReadWriteFile)

            # Test text sanitization
            raw_text = UnsanitizedText(f"File at {root}/ws/{fname} executed.")
            clean_text = fake.sanitize_text(raw_text)
            self.assertNotIn(f"{root}/ws/{fname}", clean_text)
            self.assertIn(rel, clean_text)
