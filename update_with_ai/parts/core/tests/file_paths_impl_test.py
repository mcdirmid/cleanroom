# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T02:54:02Z
# CHANGE: Inspect message field on PathValidationError instead of str(ctx.exception)
# CODE_HASH: 86753e1b71b9
# COVERAGE_AUDIT: 2026-10-09T21:19:01Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for file_paths_impl per its grounding specification."""

from __future__ import annotations

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.core.lib.file_paths_impl import (
    FilePathManager,
    __initialize__,
)


def _make_path_string(path: str) -> file_paths.PathString:
    return file_paths.PathString(path)


class FilePathsImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_initialization(self) -> None:
        """CUJ: Verify initial component presence and singleton resolution."""
        self.assertIsNotNone(self.registry)
        with enter_phase(system, registry=self.registry) as scope:
            manager = scope.get_singleton(FilePathManager)
            self.assertIsNotNone(manager)

    def test_create_host_path_valid(self) -> None:
        """Postcondition: MUST return a host path encapsulating the path string."""
        with enter_phase(system, registry=self.registry) as scope:
            manager = scope.get_singleton(FilePathManager)
            host_path = manager.create_host_path(_make_path_string("some/path"))
            self.assertEqual(host_path.path, "some/path")

    def test_create_absolute_path_valid(self) -> None:
        """Postcondition: MUST validate that the path is absolute and return an absolute path."""
        with enter_phase(system, registry=self.registry) as scope:
            manager = scope.get_singleton(FilePathManager)
            abs_path = manager.create_absolute_path(_make_path_string("/var/log/app.log"))
            self.assertEqual(abs_path.path, "/var/log/app.log")

    def test_create_absolute_path_not_absolute_raises(self) -> None:
        """Postcondition: WHEN path is not absolute, MUST raise PathValidationError."""
        with enter_phase(system, registry=self.registry) as scope:
            manager = scope.get_singleton(FilePathManager)
            path_str = _make_path_string("relative/path")
            with self.assertRaises(file_paths.PathValidationError) as ctx:
                manager.create_absolute_path(path_str)
            self.assertEqual(ctx.exception.message, "Path is not absolute: relative/path")

    def test_create_workspace_path_valid(self) -> None:
        """Postcondition: MUST validate that the path is relative and return a workspace path."""
        with enter_phase(system, registry=self.registry) as scope:
            manager = scope.get_singleton(FilePathManager)
            ws_path = manager.create_workspace_path(_make_path_string("parts/core/file.py"))
            self.assertEqual(ws_path.path, "parts/core/file.py")

    def test_create_workspace_path_absolute_raises(self) -> None:
        """Postcondition: WHEN path is absolute, MUST raise PathValidationError."""
        with enter_phase(system, registry=self.registry) as scope:
            manager = scope.get_singleton(FilePathManager)
            path_str = _make_path_string("/parts/core/file.py")
            with self.assertRaises(file_paths.PathValidationError) as ctx:
                manager.create_workspace_path(path_str)
            self.assertEqual(
                ctx.exception.message,
                "Workspace path must be relative, got absolute: /parts/core/file.py",
            )

    def test_resolve_path(self) -> None:
        """Postcondition: MUST produce combined absolute path formed by joining root and relative."""
        with enter_phase(system, registry=self.registry) as scope:
            manager = scope.get_singleton(FilePathManager)
            root = manager.create_absolute_path(_make_path_string("/workspace/project"))
            relative = manager.create_workspace_path(_make_path_string("src/main.py"))
            resolved = manager.resolve_path(root, relative)
            self.assertEqual(resolved.path, "/workspace/project/src/main.py")


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
