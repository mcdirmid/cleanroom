"""Unit tests for file_paths_impl aligned with grounding specifications."""

import os
import unittest
from update_with_ai.parts.core.lib.file_paths import (
    FilePathManager,

    HostPath,
    AbsolutePath,
    WorkspacePath,
    DirectoryPath,
    WorkspaceRoot,
)
from update_with_ai.parts.core.lib.file_paths_impl import (
    FilePathManager as FilePathManagerImpl,

    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase


class TestFilePathsImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_create_host_path(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            hp = service.create_host_path("/any/path/file.txt")
            # Requirement: [FilePaths] Returns a host path encapsulating the path string.
            self.assertIsInstance(hp, HostPath)
            self.assertEqual(hp.path, "/any/path/file.txt")

    def test_create_absolute_path(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            ap = service.create_absolute_path("/var/log/app.log")
            # Requirement: [FilePaths] If the path string is absolute, returns an absolute path encapsulating the path string.
            self.assertIsInstance(ap, AbsolutePath)
            self.assertIsInstance(ap, HostPath)
            self.assertEqual(ap.path, "/var/log/app.log")

            # Requirement: [FilePaths] If the path string is not absolute, raises a failure.
            with self.assertRaises(ValueError):
                service.create_absolute_path("relative/path/app.log")

    def test_create_workspace_path(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            wp = service.create_workspace_path("src/lib/app.py")
            # Requirement: [FilePaths] If the path string is relative, returns a workspace path encapsulating the path string.
            self.assertIsInstance(wp, WorkspacePath)
            self.assertIsInstance(wp, HostPath)
            self.assertEqual(wp.path, "src/lib/app.py")

            # Requirement: [FilePaths] If the path string is absolute, raises a failure.
            with self.assertRaises(ValueError):
                service.create_workspace_path("/absolute/path")

    def test_create_directory_path(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            dp = service.create_directory_path("/tmp/output")
            # Requirement: [FilePaths] If the path string is absolute, returns a directory path encapsulating the path string.
            self.assertIsInstance(dp, DirectoryPath)
            self.assertIsInstance(dp, AbsolutePath)
            self.assertEqual(dp.path, "/tmp/output")

            # Requirement: [FilePaths] If the path string is not absolute, raises a failure.
            with self.assertRaises(ValueError):
                service.create_directory_path("relative/dir")

    def test_get_workspace_root_with_env(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            old_env = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            try:
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = "/custom/workspace"
                root = service.get_workspace_root()
                # Requirement: [FilePaths] Returns a workspace root representing the physical workspace root directory.
                self.assertIsInstance(root, WorkspaceRoot)
                self.assertIsInstance(root, DirectoryPath)
                self.assertEqual(root.path, "/custom/workspace")
            finally:
                if old_env is not None:
                    os.environ["BUILD_WORKSPACE_DIRECTORY"] = old_env
                else:
                    os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)

    def test_get_workspace_root_fallback(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            old_env = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            try:
                os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)
                root = service.get_workspace_root()
                # Requirement: [FilePaths] Returns a workspace root representing the physical workspace root directory.
                self.assertIsInstance(root, WorkspaceRoot)
                self.assertEqual(root.path, os.path.normpath(os.getcwd()))
            finally:
                if old_env is not None:
                    os.environ["BUILD_WORKSPACE_DIRECTORY"] = old_env

    def test_resolve_directory_and_path(self) -> None:
        with enter_phase("system", registry=self.registry) as scope:
            service = scope.get_singleton(FilePathManager)
            old_env = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            try:
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = "/workspace/root"
                root = service.get_workspace_root()
                rel_dir = service.create_workspace_path("testing/specs")
                resolved_dir = service.resolve_directory(root, rel_dir)
                # Requirement: [FilePaths] Returns a directory path formed by joining the workspace root and the workspace path.
                self.assertIsInstance(resolved_dir, DirectoryPath)
                self.assertEqual(resolved_dir.path, "/workspace/root/testing/specs")

                rel_file = service.create_workspace_path(
                    "testing/specs/.update_with_ai.textproto"
                )
                resolved_file = service.resolve_path(root, rel_file)
                # Requirement: [FilePaths] Returns an absolute path formed by joining the workspace root and the workspace path.
                self.assertIsInstance(resolved_file, AbsolutePath)
                self.assertEqual(
                    resolved_file.path,
                    "/workspace/root/testing/specs/.update_with_ai.textproto",
                )
            finally:
                if old_env is not None:
                    os.environ["BUILD_WORKSPACE_DIRECTORY"] = old_env
                else:
                    os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
