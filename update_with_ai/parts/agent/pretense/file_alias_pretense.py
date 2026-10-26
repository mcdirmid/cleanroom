"""Pretense state machine, fake synthesis, unit tests, and property fuzzing for AliasManager."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import unittest

from hypothesis import given, settings, strategies as st

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


proto = StateMachineProto[AliasManagerState]()


# ==============================================================================
# 1. Seeding Transitions
# ==============================================================================

@proto.seeding()
def seed_workspace_root(): pass

@seed_workspace_root.arguments
def _(
    state: AliasManagerState,
    this: Any,
    workspace_root: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    root = "/workspace" if isinstance(workspace_root, NotBoundType) else str(workspace_root)
    return (root,)

@seed_workspace_root.provide
def _(
    state: AliasManagerState,
    this: Any,
    workspace_root: str,
    result: None = None,
) -> None:
    state.workspace_root = workspace_root


@proto.seeding()
def seed_bound_file(): pass

@seed_bound_file.arguments
def _(
    state: AliasManagerState,
    this: Any,
    relative_path: str | NotBoundType = NotBound,
    workspace_path: Optional[str] | NotBoundType = NotBound,
    owning_unit: Optional[str] | NotBoundType = NotBound,
    owning_role: Optional[str] | NotBoundType = NotBound,
    is_readonly: bool | NotBoundType = NotBound,
) -> Optional[Tuple[str, str, str, str, bool]]:
    rel = "lib/module.py" if isinstance(relative_path, NotBoundType) else str(relative_path)
    ws = f"src/{rel}" if isinstance(workspace_path, NotBoundType) or workspace_path is None else str(workspace_path)
    unit = "target" if isinstance(owning_unit, NotBoundType) or owning_unit is None else str(owning_unit)
    role = "lib" if isinstance(owning_role, NotBoundType) or owning_role is None else str(owning_role)
    ro = False if isinstance(is_readonly, NotBoundType) else bool(is_readonly)
    return (rel, ws, unit, role, ro)

@seed_bound_file.provide
def _(
    state: AliasManagerState,
    this: Any,
    relative_path: str,
    workspace_path: str,
    owning_unit: str,
    owning_role: str,
    is_readonly: bool,
    result: None = None,
) -> None:
    cls = ReadOnlyFile if is_readonly else ReadWriteFile
    bf = cls(
        relative_path=RelativePath(relative_path),
        workspace_path=file_paths.WorkspacePath(file_paths.PathString(workspace_path)),
        owning_node=DagNode(UnitAddress(owning_unit), RoleAddress(owning_role)),
    )
    state.bound_files[relative_path] = bf


# ==============================================================================
# 2. Interface Transitions
# ==============================================================================

@proto.transition(name="workspace_root")
def workspace_root(): pass

@workspace_root.returns
def _(state: AliasManagerState, this: Any, outcome: object = NotBound) -> Optional[Outcome[file_paths.WorkspaceRoot]]:
    expected = file_paths.WorkspaceRoot(file_paths.PathString(state.workspace_root))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(AliasManager.to_alias)
def to_alias(): pass

@to_alias.arguments
def _(
    state: AliasManagerState,
    this: Any,
    path: str | NotBoundType = NotBound,
) -> Optional[Tuple[str]]:
    if isinstance(path, NotBoundType):
        if state.bound_files:
            return (next(iter(state.bound_files.keys())),)
        return ("demo.py",)
    return (str(path),)

@to_alias.returns
def _(
    state: AliasManagerState,
    this: Any,
    path: str,
    outcome: object = NotBound,
) -> Optional[Outcome[FileAlias]]:
    p_str = str(path)
    # Direct match on relative path
    if p_str in state.bound_files:
        expected: FileAlias = state.bound_files[p_str]
    elif p_str in state.unbound_files:
        expected = state.unbound_files[p_str]
    else:
        # Match by basename if unique
        base = os.path.basename(p_str)
        basename_matches = [bf for bf in state.bound_files.values() if os.path.basename(bf.relative_path) == base]
        if len(basename_matches) == 1:
            expected = basename_matches[0]
        else:
            expected = UnboundFile(relative_path=RelativePath(p_str))

    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


@proto.transition(AliasManager.sanitize_text)
def sanitize_text(): pass

@sanitize_text.arguments
def _(
    state: AliasManagerState,
    this: Any,
    text: str | NotBoundType = NotBound,
) -> Optional[Tuple[UnsanitizedText]]:
    t = "Hello /workspace/src/lib/module.py" if isinstance(text, NotBoundType) else str(text)
    return (UnsanitizedText(t),)

@sanitize_text.returns
def _(
    state: AliasManagerState,
    this: Any,
    text: UnsanitizedText,
    outcome: object = NotBound,
) -> Optional[Outcome[SanitizedText]]:
    res = str(text)
    # Mask absolute paths for bound files
    root = state.workspace_root.rstrip("/")
    for rel_path, bf in sorted(state.bound_files.items(), key=lambda item: len(item[1].workspace_path.path), reverse=True):
        ws_norm = os.path.normpath(bf.workspace_path.path)
        abs_p = os.path.normpath(f"{root}/{ws_norm}")
        if abs_p in res:
            res = res.replace(abs_p, rel_path)
        if ws_norm in res:
            res = res.replace(ws_norm, rel_path)
    if root and root in res:
        res = res.replace(f"{root}/", "").replace(root, "")

    expected = SanitizedText(res)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None


# ==============================================================================
# 3. Helper Factory
# ==============================================================================

def make_alias_manager_fake(state: Optional[AliasManagerState] = None) -> AliasManager:
    """Instantiate a synthesized AliasManager fake with Pretense."""
    st = state or AliasManagerState()
    sm = proto.make_state_machine(st)
    return sm.as_fake(AliasManager)


# ==============================================================================
# 4. Unit Tests
# ==============================================================================

class TestAliasManagerUnit(unittest.TestCase):
    """Unit tests verifying synthesized AliasManager fake."""

    def setUp(self) -> None:
        self.state = AliasManagerState(workspace_root="/home/user/project")
        self.sm = proto.make_state_machine(self.state)
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
        sm = proto.make_state_machine(state)
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
