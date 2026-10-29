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
from pretense import (
    Domain,
    Raised,
    StateMachine,
    TransitionContext,
    get_current_draw,
    transition,
)
from pretense.compiler import compile_hypothesis_test_case
from pretense.sentinels import NotBound, NotBoundType
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


class FilePathManagerStateMachine(StateMachine[FilePathManagerState]):
    """Unified Pretense State Machine for FilePathManager."""

    def __init__(
        self,
        state: Optional[FilePathManagerState] = None,
        singletons: Optional[dict[type[Any], Any]] = None,
    ) -> None:
        super().__init__(state=state or FilePathManagerState(), singletons=singletons)

    @transition(FilePathManager.create_host_path)
    def create_host_path(
        self,
        ctx: TransitionContext[FilePathManager, [PathString | str], HostPath],
    ) -> None:
        ctx.arguments(
            path=Domain(
                strategy=st.text(min_size=1, max_size=30).filter(lambda s: "\x00" not in s),
                validator=lambda p: isinstance(p, str),
            )
        )
        ctx.returns(lambda path: HostPath(path=PathString(str(path))))
        ctx.update(lambda res, path: self.state.created_host_paths.append(res))

    @transition(FilePathManager.create_absolute_path)
    def create_absolute_path(
        self,
        ctx: TransitionContext[FilePathManager, [PathString | str], AbsolutePath],
    ) -> None:
        ctx.arguments(
            path=Domain(
                strategy=st.one_of(
                    st.from_regex(r"^/[a-z0-9_-]{1,15}$", fullmatch=True),
                    st.from_regex(r"^[a-z0-9_-]{1,15}$", fullmatch=True),
                ),
                validator=lambda p: isinstance(p, str),
            )
        )
        def returns(path: PathString | str) -> Any:
            raw = str(path)
            if raw.startswith("/") and "\x00" not in raw:
                return AbsolutePath(path=PathString(raw))
            return Raised(PathValidationError(ValidationMessage(f"Path must be absolute: {raw}")))
        ctx.returns(returns)
        def provide(res: Any, path: PathString | str) -> None:
            if isinstance(res, AbsolutePath):
                self.state.created_absolute_paths.append(res)
        ctx.update(provide)

    @transition(FilePathManager.create_workspace_path)
    def create_workspace_path(
        self,
        ctx: TransitionContext[FilePathManager, [PathString | str], WorkspacePath],
    ) -> None:
        ctx.arguments(
            path=Domain(
                strategy=st.one_of(
                    st.from_regex(r"^src/[a-z0-9_-]{1,15}\.py$", fullmatch=True),
                    st.from_regex(r"^/invalid/[a-c]{1,10}$", fullmatch=True),
                ),
                validator=lambda p: isinstance(p, str),
            )
        )
        def returns(path: PathString | str) -> Any:
            raw = str(path)
            is_valid = not raw.startswith("/") and not raw.startswith("\\") and ".." not in raw.split("/") and "\x00" not in raw
            if is_valid:
                return WorkspacePath(path=PathString(raw))
            return Raised(PathValidationError(ValidationMessage(f"Path must be relative workspace path: {raw}")))
        ctx.returns(returns)
        def provide(res: Any, path: PathString | str) -> None:
            if isinstance(res, WorkspacePath):
                self.state.created_workspace_paths.append(res)
        ctx.update(provide)

    @transition(FilePathManager.resolve_path)
    def resolve_path(
        self,
        ctx: TransitionContext[FilePathManager, [AbsolutePath, WorkspacePath], AbsolutePath],
    ) -> None:
        ctx.arguments(
            root=Domain(
                strategy=lambda draw: (
                    draw(st.sampled_from(self.state.created_absolute_paths))
                    if self.state.created_absolute_paths
                    else AbsolutePath(PathString("/workspace"))
                ),
                validator=lambda r: isinstance(r, AbsolutePath),
            ),
            relative=Domain(
                strategy=lambda draw: (
                    draw(st.sampled_from(self.state.created_workspace_paths))
                    if self.state.created_workspace_paths
                    else WorkspacePath(PathString("file.txt"))
                ),
                validator=lambda rel: isinstance(rel, WorkspacePath),
            ),
        )
        def returns(root: AbsolutePath, relative: WorkspacePath) -> AbsolutePath:
            norm_root = str(root.path).rstrip("/")
            joined = f"{norm_root}/{str(relative.path)}"
            return AbsolutePath(PathString(joined))
        ctx.returns(returns)
        ctx.update(lambda res, root, relative: self.state.resolved_paths.append((root, relative, res)))


proto = FilePathManagerStateMachine()


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
