# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 0aaa1728c001
# COVERAGE_AUDIT: 2026-10-05T20:52:01Z
# QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for file_paths_impl aligned with grounding specifications."""

import unittest
from support.lib.lifecycle import LifecycleRegistry, enter_phase
from update_with_ai.parts.core.lib.file_paths import (
    AbsolutePath,
    FilePathManager,
    HostPath,
    PathString,
    PathValidationError,
    WorkspacePath,
    WorkspaceRoot,
)
from update_with_ai.parts.core.lib.file_paths_impl import (
    FilePathManager as FilePathManagerImpl,
    __initialize__,
)


class TestFilePathsImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_create_host_path(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            hp = service.create_host_path(PathString("/any/path/file.txt"))
            # Requirement: MUST return a host path encapsulating the path string.
            self.assertIsInstance(hp, HostPath)
            self.assertEqual(hp.path, "/any/path/file.txt")

    def test_create_absolute_path(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            # Requirement: MUST validate that the path is absolute and return an absolute path encapsulating the path string.
            ap = service.create_absolute_path(PathString("/var/log/app.log"))
            self.assertIsInstance(ap, AbsolutePath)
            self.assertIsInstance(ap, HostPath)
            self.assertEqual(ap.path, "/var/log/app.log")

            # Requirement: WHEN the path is not absolute, MUST raise PathValidationError with diagnostic feedback formatted as "Path is not absolute: {path}".
            with self.assertRaises(PathValidationError) as ctx:
                service.create_absolute_path(PathString("relative/path/app.log"))
            self.assertEqual(
                str(ctx.exception), "Path is not absolute: relative/path/app.log"
            )

    def test_create_workspace_path(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            # Requirement: MUST validate that the path is relative without leading path separators and return a workspace path encapsulating the path string.
            wp = service.create_workspace_path(PathString("src/lib/app.py"))
            self.assertIsInstance(wp, WorkspacePath)
            self.assertIsInstance(wp, HostPath)
            self.assertEqual(wp.path, "src/lib/app.py")

            # Requirement: WHEN the path is absolute or has leading path separators, MUST raise PathValidationError with diagnostic feedback formatted as "Workspace path must be relative, got absolute: {path}".
            with self.assertRaises(PathValidationError) as ctx:
                service.create_workspace_path(PathString("/absolute/path"))
            self.assertEqual(
                str(ctx.exception),
                "Workspace path must be relative, got absolute: /absolute/path",
            )

            with self.assertRaises(PathValidationError) as ctx2:
                service.create_workspace_path(PathString("/leading/slash"))
            self.assertEqual(
                str(ctx2.exception),
                "Workspace path must be relative, got absolute: /leading/slash",
            )

    def test_resolve_path(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            root = service.create_absolute_path(PathString("/workspace/root"))
            rel_file = service.create_workspace_path(
                PathString("testing/specs/.update_with_ai.textproto")
            )
            # Requirement: MUST produce the combined absolute path formed by joining the workspace root and the relative workspace path.
            resolved_file = service.resolve_path(root, rel_file)
            self.assertIsInstance(resolved_file, AbsolutePath)
            self.assertEqual(
                resolved_file.path,
                "/workspace/root/testing/specs/.update_with_ai.textproto",
            )

    def test_workspace_root_type(self) -> None:
        root = WorkspaceRoot(PathString("/workspace/root"))
        self.assertIsInstance(root, AbsolutePath)
        self.assertIsInstance(root, HostPath)
        self.assertEqual(root.path, "/workspace/root")


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
