"""Pretense State Machine, Unit Tests, and Fuzzer for FilePathManager (file_paths_impl).

Models path representation, validation, and resolution per low/file_paths.pyi.
Synthesizes in-memory fakes and drives concrete FilePathManager implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, List, Optional, Tuple
import unittest

import hypothesis.strategies as st
from pretense.compiler import compile_hypothesis_test_case
from pretense.context import get_current_draw
from pretense.proto import StateMachineProto
from pretense.sentinels import NotBound, NotBoundType, Outcome, Raised, Value
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton, system
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.core.lib.file_paths import (
    AbsolutePath,
    FilePathManager,
    HostPath,
    PathString,
    PathValidationError,
    ValidationMessage,
    WorkspacePath,
)
from update_with_ai.parts.core.lib.file_paths_impl import (
    FilePathManager as FilePathManagerImpl,
    __initialize__,
)


# ==============================================================================
# 1. State Machine Specification (Model & Transitions)
# ==============================================================================

@dataclass
class FilePathManagerState:
    """Canonical model state for FilePathManager operations."""
    created_host_paths: List[HostPath] = field(default_factory=list)
    created_absolute_paths: List[AbsolutePath] = field(default_factory=list)
    created_workspace_paths: List[WorkspacePath] = field(default_factory=list)
    resolved_paths: List[Tuple[AbsolutePath, WorkspacePath, AbsolutePath]] = field(
        default_factory=list
    )


proto = StateMachineProto[FilePathManagerState]()


# ------------------------------------------------------------------------------
# 1.1 create_host_path
# ------------------------------------------------------------------------------

@proto.transition(FilePathManager.create_host_path)
def create_host_path(): pass

@create_host_path.arguments
def _(
    state: FilePathManagerState,
    this: Any,
    path: PathString | str | NotBoundType = NotBound,
) -> Optional[Tuple[PathString]]:
    if isinstance(path, NotBoundType):
        draw = get_current_draw()
        if draw is not None:
            raw = draw(st.text(min_size=1, max_size=30).filter(lambda s: "\x00" not in s))
        else:
            raw = f"host_path_{len(state.created_host_paths)}"
        resolved_path = PathString(raw)
    else:
        resolved_path = PathString(str(path))
    return (resolved_path,)

@create_host_path.returns
def _(
    state: FilePathManagerState,
    this: Any,
    path: PathString,
    outcome: object = NotBound,
) -> Optional[Outcome[HostPath]]:
    expected = HostPath(path=path)
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@create_host_path.provide
def _(
    state: FilePathManagerState,
    this: Any,
    path: PathString,
    result: HostPath,
) -> None:
    state.created_host_paths.append(result)


# ------------------------------------------------------------------------------
# 1.2 create_absolute_path
# ------------------------------------------------------------------------------

@proto.transition(FilePathManager.create_absolute_path)
def create_absolute_path(): pass

@create_absolute_path.arguments
def _(
    state: FilePathManagerState,
    this: Any,
    path: PathString | str | NotBoundType = NotBound,
) -> Optional[Tuple[PathString]]:
    if isinstance(path, NotBoundType):
        draw = get_current_draw()
        if draw is not None:
            # 80% valid absolute, 20% invalid relative
            is_valid = draw(st.booleans()) and draw(st.booleans())
            if is_valid:
                seg = draw(st.text(min_size=1, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-"))
                raw = f"/{seg}"
            else:
                raw = draw(st.text(min_size=1, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-"))
        else:
            raw = f"/abs_path_{len(state.created_absolute_paths)}"
        resolved_path = PathString(raw)
    else:
        resolved_path = PathString(str(path))
    return (resolved_path,)

@create_absolute_path.returns
def _(
    state: FilePathManagerState,
    this: Any,
    path: PathString,
    outcome: object = NotBound,
) -> Optional[Outcome[AbsolutePath]]:
    raw = str(path)
    is_valid = raw.startswith("/") and "\x00" not in raw
    if is_valid:
        expected = AbsolutePath(path=path)
        if isinstance(outcome, Value) and outcome.val == expected:
            return outcome
        if outcome is NotBound:
            return Value(expected)
        return None
    else:
        # Invalid absolute path must raise PathValidationError
        if isinstance(outcome, Raised) and isinstance(outcome.exc, PathValidationError):
            return outcome
        if outcome is NotBound:
            return Raised(PathValidationError(ValidationMessage(f"Path must be absolute: {raw}")))
        return None

@create_absolute_path.provide
def _(
    state: FilePathManagerState,
    this: Any,
    path: PathString,
    result: AbsolutePath,
) -> None:
    state.created_absolute_paths.append(result)


# ------------------------------------------------------------------------------
# 1.3 create_workspace_path
# ------------------------------------------------------------------------------

@proto.transition(FilePathManager.create_workspace_path)
def create_workspace_path(): pass

@create_workspace_path.arguments
def _(
    state: FilePathManagerState,
    this: Any,
    path: PathString | str | NotBoundType = NotBound,
) -> Optional[Tuple[PathString]]:
    if isinstance(path, NotBoundType):
        draw = get_current_draw()
        if draw is not None:
            # 80% valid relative workspace path, 20% invalid (absolute or with ..)
            is_valid = draw(st.booleans()) and draw(st.booleans())
            if is_valid:
                seg = draw(st.text(min_size=1, max_size=15, alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-"))
                raw = f"src/{seg}.py"
            else:
                raw = f"/invalid/{draw(st.text(min_size=1, max_size=10, alphabet='abc'))}"
        else:
            raw = f"ws_path_{len(state.created_workspace_paths)}"
        resolved_path = PathString(raw)
    else:
        resolved_path = PathString(str(path))
    return (resolved_path,)

@create_workspace_path.returns
def _(
    state: FilePathManagerState,
    this: Any,
    path: PathString,
    outcome: object = NotBound,
) -> Optional[Outcome[WorkspacePath]]:
    raw = str(path)
    is_valid = not raw.startswith("/") and not raw.startswith("\\") and ".." not in raw.split("/") and "\x00" not in raw
    if is_valid:
        expected = WorkspacePath(path=path)
        if isinstance(outcome, Value) and outcome.val == expected:
            return outcome
        if outcome is NotBound:
            return Value(expected)
        return None
    else:
        if isinstance(outcome, Raised) and isinstance(outcome.exc, PathValidationError):
            return outcome
        if outcome is NotBound:
            return Raised(PathValidationError(ValidationMessage(f"Path must be relative workspace path: {raw}")))
        return None

@create_workspace_path.provide
def _(
    state: FilePathManagerState,
    this: Any,
    path: PathString,
    result: WorkspacePath,
) -> None:
    state.created_workspace_paths.append(result)


# ------------------------------------------------------------------------------
# 1.4 resolve_path
# ------------------------------------------------------------------------------

@proto.transition(FilePathManager.resolve_path)
def resolve_path(): pass

@resolve_path.arguments
def _(
    state: FilePathManagerState,
    this: Any,
    root: AbsolutePath | NotBoundType = NotBound,
    relative: WorkspacePath | NotBoundType = NotBound,
) -> Optional[Tuple[AbsolutePath, WorkspacePath]]:
    if isinstance(root, NotBoundType):
        if state.created_absolute_paths:
            r = state.created_absolute_paths[0]
        else:
            r = AbsolutePath(PathString("/workspace"))
    else:
        r = root

    if isinstance(relative, NotBoundType):
        if state.created_workspace_paths:
            rel = state.created_workspace_paths[0]
        else:
            rel = WorkspacePath(PathString("file.txt"))
    else:
        rel = relative

    return (r, rel)

@resolve_path.returns
def _(
    state: FilePathManagerState,
    this: Any,
    root: AbsolutePath,
    relative: WorkspacePath,
    outcome: object = NotBound,
) -> Optional[Outcome[AbsolutePath]]:
    norm_root = str(root.path).rstrip("/")
    joined = f"{norm_root}/{str(relative.path)}"
    expected = AbsolutePath(PathString(joined))
    if isinstance(outcome, Value) and outcome.val == expected:
        return outcome
    if outcome is NotBound:
        return Value(expected)
    return None

@resolve_path.provide
def _(
    state: FilePathManagerState,
    this: Any,
    root: AbsolutePath,
    relative: WorkspacePath,
    result: AbsolutePath,
) -> None:
    state.resolved_paths.append((root, relative, result))


# ==============================================================================
# 2. Deterministic Unit Tests (Regression Suite)
# ==============================================================================

class TestFilePathManagerUnit(unittest.TestCase):
    """Verifies that Pretense synthesizes sound in-memory fakes and drives FilePathManager."""

    def setUp(self) -> None:
        self.state = FilePathManagerState()
        self.sm = proto.make_state_machine(self.state)
        self.fake_manager = self.sm.as_fake(file_paths.FilePathManager)

    def test_fake_create_host_path(self) -> None:
        hp = self.fake_manager.create_host_path(PathString("foo/bar"))
        self.assertEqual(hp.path, "foo/bar")
        self.assertEqual(len(self.state.created_host_paths), 1)

    def test_fake_create_absolute_path(self) -> None:
        ap = self.fake_manager.create_absolute_path(PathString("/var/log"))
        self.assertEqual(ap.path, "/var/log")

    def test_fake_create_absolute_path_invalid_raises(self) -> None:
        with self.assertRaises(PathValidationError):
            self.fake_manager.create_absolute_path(PathString("relative/path"))

    def test_fake_create_workspace_path(self) -> None:
        wp = self.fake_manager.create_workspace_path(PathString("src/main.py"))
        self.assertEqual(wp.path, "src/main.py")

    def test_fake_create_workspace_path_invalid_raises(self) -> None:
        with self.assertRaises(PathValidationError):
            self.fake_manager.create_workspace_path(PathString("/leading/slash"))

    def test_fake_resolve_path(self) -> None:
        root = self.fake_manager.create_absolute_path(PathString("/workspace/root"))
        rel = self.fake_manager.create_workspace_path(PathString("subdir/file.txt"))
        resolved = self.fake_manager.resolve_path(root, rel)
        self.assertEqual(resolved.path, "/workspace/root/subdir/file.txt")

    def test_parity_across_path_forms(self) -> None:
        registry = LifecycleRegistry()
        __initialize__(registry)
        with enter_phase(system, registry=registry):
            real_mgr = get_singleton(file_paths.FilePathManager)
            sm = proto.make_state_machine(FilePathManagerState())
            fake_mgr = sm.as_fake(file_paths.FilePathManager)

            # Test host path parity
            self.assertEqual(
                real_mgr.create_host_path(PathString("a/b")),
                fake_mgr.create_host_path(PathString("a/b")),
            )

            # Test absolute path parity
            self.assertEqual(
                real_mgr.create_absolute_path(PathString("/opt/bin")),
                fake_mgr.create_absolute_path(PathString("/opt/bin")),
            )
            with self.assertRaises(PathValidationError):
                real_mgr.create_absolute_path(PathString("relative/path"))

            # Test workspace path parity
            self.assertEqual(
                real_mgr.create_workspace_path(PathString("docs/readme.md")),
                fake_mgr.create_workspace_path(PathString("docs/readme.md")),
            )
            with self.assertRaises(PathValidationError):
                real_mgr.create_workspace_path(PathString("/leading/slash"))
            with self.assertRaises(PathValidationError):
                real_mgr.create_workspace_path(PathString("/abs/path"))

            # Test resolution parity
            root = PathString("/repo/root")
            rel = PathString("parts/core")
            self.assertEqual(
                real_mgr.resolve_path(
                    real_mgr.create_absolute_path(root),
                    real_mgr.create_workspace_path(rel),
                ),
                fake_mgr.resolve_path(
                    fake_mgr.create_absolute_path(root),
                    fake_mgr.create_workspace_path(rel),
                ),
            )


# ==============================================================================
# 3. Hypothesis Stateful Fuzzer
# ==============================================================================

def make_sut() -> FilePathManager:
    registry = LifecycleRegistry()
    __initialize__(registry)
    scope = enter_phase(system, registry=registry)
    scope.__enter__()
    return get_singleton(file_paths.FilePathManager)


FilePathManagerFuzzTest = compile_hypothesis_test_case(
    proto=proto,
    sut_factory=make_sut,
    initial_state_factory=FilePathManagerState,
    name="FilePathManagerFuzzTest",
)
