#!/usr/bin/env python3
"""cleanroom_uv_runner_test.py — Unit tests for standalone UV runner and path scope resolution."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
for _p in [
    _repo_root,
    os.path.join(_repo_root, "update_python_with_ai"),
    os.path.join(_repo_root, "update_with_ai"),
    os.path.join(_repo_root, "update_with_ai/support/lib"),
    os.path.join(_repo_root, "update_python_with_ai/support/lib"),
]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

import shutil
from support.lib.lifecycle import get_singleton
from update_with_ai.parts.metadata.lib import src_metadata
from update_with_ai.parts.systems.lib import cleanroom_asm
from update_with_ai.parts.uv.lib import manifest_loader
from update_with_ai.support.lib import cleanroom_uv_runner


class CleanroomUvRunnerTest(unittest.TestCase):
    target_scope: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        cleanroom_asm.__initialize__()
        cls.loader = get_singleton(manifest_loader.UvManifestLoader)
        cls.repo_root = _repo_root
        for entry in sorted(os.listdir(_repo_root)):
            if entry.startswith((".", "bazel-", "venv")):
                continue
            cand = os.path.join(_repo_root, entry, "parts", "sandbox")
            if os.path.isdir(cand):
                cls.target_scope = entry
                break

    def test_resolve_scope_entire_scope(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            self.target_scope, self.repo_root, self.loader
        )
        self.assertIsNotNone(nodes)
        assert nodes is not None
        self.assertGreater(len(nodes), 100)
        # Verify first tier is high
        self.assertEqual(nodes[0].role_address, "high")
        # Verify last tier is coverage
        self.assertEqual(nodes[-1].role_address, "coverage")

    def test_resolve_scope_part(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            f"{self.target_scope}/parts/sandbox", self.repo_root, self.loader
        )
        self.assertIsNotNone(nodes)
        assert nodes is not None
        self.assertEqual(len(nodes), 109)
        roles = {n.role_address for n in nodes}
        self.assertIn("scenario", roles)
        for n in nodes:
            self.assertTrue(n.unit_address.startswith(f"//{self.target_scope}/parts/sandbox:"))

    def test_resolve_scope_part_role(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            f"{self.target_scope}/parts/sandbox/lib", self.repo_root, self.loader
        )
        self.assertIsNotNone(nodes)
        assert nodes is not None
        self.assertEqual(len(nodes), 15)
        for n in nodes:
            self.assertTrue(n.unit_address.startswith(f"//{self.target_scope}/parts/sandbox:"))
            self.assertEqual(n.role_address, "lib")

    def test_resolve_scope_single_file(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            f"{self.target_scope}/parts/sandbox/lib/file_reader_impl.py",
            self.repo_root,
            self.loader,
        )
        self.assertIsNotNone(nodes)
        assert nodes is not None
        self.assertEqual(len(nodes), 1)
        self.assertEqual(
            nodes[0].unit_address, f"//{self.target_scope}/parts/sandbox:file_reader_impl"
        )
        self.assertEqual(nodes[0].role_address, "lib")

    def test_resolve_scope_label_target_returns_none(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            f"//{self.target_scope}/parts/systems:cleanroom_asm#coverage",
            self.repo_root,
            self.loader,
        )
        self.assertIsNone(nodes)

    def test_resolve_scope_part_explicit_role(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            f"//{self.target_scope}/parts/sandbox#spec_qa",
            self.repo_root,
            self.loader,
        )
        self.assertIsNotNone(nodes)
        assert nodes is not None
        self.assertEqual(len(nodes), 15)
        for n in nodes:
            self.assertTrue(n.unit_address.startswith(f"//{self.target_scope}/parts/sandbox:"))
            self.assertEqual(n.role_address, "spec_qa")

    def test_resolve_scope_up_to_role(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            f"{self.target_scope}/parts/sandbox",
            self.repo_root,
            self.loader,
            up_to_role="low",
        )
        self.assertIsNotNone(nodes)
        assert nodes is not None
        roles = {n.role_address for n in nodes}
        self.assertIn("high", roles)
        self.assertIn("planning", roles)
        self.assertIn("low", roles)
        self.assertNotIn("lib", roles)
        self.assertNotIn("test", roles)

    def test_run_cleanroom_target_mark_clean_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "cleanroom.toml"), "w", encoding="utf-8") as f:
                f.write('methodology = "//pkg"\n')
            pkg_dir = os.path.join(tmp_dir, "pkg")
            parts_dir = os.path.join(pkg_dir, "parts", "sample")
            high_dir = os.path.join(parts_dir, "high")
            lib_dir = os.path.join(parts_dir, "lib")
            os.makedirs(high_dir, exist_ok=True)
            os.makedirs(lib_dir, exist_ok=True)

            roles_src = os.path.abspath(os.path.join(self.repo_root, "update_python_with_ai/cleanroom_roles.toml"))
            if os.path.isfile(roles_src):
                shutil.copyfile(roles_src, os.path.join(pkg_dir, "cleanroom_roles.toml"))

            with open(os.path.join(high_dir, "sample.md"), "w", encoding="utf-8") as f:
                f.write("# Sample High Level Spec\n\n```python\n# Component: implementation\n```\n")
            with open(os.path.join(lib_dir, "sample.py"), "w", encoding="utf-8") as f:
                f.write("# sample implementation\n")

            orig_cwd = os.getcwd()
            try:
                os.chdir(tmp_dir)
                ret = cleanroom_uv_runner.run_cleanroom_target(
                    target_str="pkg/parts/sample/lib",
                    action="mark-clean",
                    workspace_dir=tmp_dir,
                )
                self.assertEqual(ret, 0)
            finally:
                os.chdir(orig_cwd)

    def test_mark_clean_skips_clean_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "cleanroom.toml"), "w", encoding="utf-8") as f:
                f.write('methodology = "//pkg"\n')
            pkg_dir = os.path.join(tmp_dir, "pkg")
            parts_dir = os.path.join(pkg_dir, "parts", "sample")
            high_dir = os.path.join(parts_dir, "high")
            lib_dir = os.path.join(parts_dir, "lib")
            os.makedirs(high_dir, exist_ok=True)
            os.makedirs(lib_dir, exist_ok=True)

            roles_src = os.path.abspath(os.path.join(self.repo_root, "update_python_with_ai/cleanroom_roles.toml"))
            if os.path.isfile(roles_src):
                shutil.copyfile(roles_src, os.path.join(pkg_dir, "cleanroom_roles.toml"))

            hls_file = os.path.join(high_dir, "sample.md")
            with open(hls_file, "w", encoding="utf-8") as f:
                f.write("# Sample High Level Spec\n\n```python\n# Component: implementation\n```\n")

            lib_file = os.path.join(lib_dir, "sample.py")
            with open(lib_file, "w", encoding="utf-8") as f:
                f.write("# sample implementation\n")

            orig_cwd = os.getcwd()
            try:
                os.chdir(tmp_dir)
                cleanroom_uv_runner.run_cleanroom_target(
                    target_str="pkg/parts/sample/high",
                    action="mark-clean",
                    workspace_dir=tmp_dir,
                )
                # First mark-clean marks the uncleaned node clean
                ret1 = cleanroom_uv_runner.run_cleanroom_target(
                    target_str="pkg/parts/sample/lib",
                    action="mark-clean",
                    workspace_dir=tmp_dir,
                )
                self.assertEqual(ret1, 0)
                meta1 = src_metadata.extract_metadata(lib_file)
                self.assertIsNotNone(meta1)
                assert meta1 is not None
                initial_last_cleaned = meta1.last_cleaned
                initial_mtime = os.path.getmtime(lib_file)

                # Second mark-clean on the now-clean node should NOT update the file
                ret2 = cleanroom_uv_runner.run_cleanroom_target(
                    target_str="pkg/parts/sample/lib",
                    action="mark-clean",
                    workspace_dir=tmp_dir,
                )
                self.assertEqual(ret2, 0)
                meta2 = src_metadata.extract_metadata(lib_file)
                assert meta2 is not None
                self.assertEqual(meta2.last_cleaned, initial_last_cleaned)
                self.assertEqual(os.path.getmtime(lib_file), initial_mtime)

                # Marking it dirty should update metadata to dirty
                ret_dirty = cleanroom_uv_runner.run_cleanroom_target(
                    target_str="pkg/parts/sample/lib",
                    action="dirty",
                    message="testing dirty",
                    workspace_dir=tmp_dir,
                )
                self.assertEqual(ret_dirty, 0)
                meta_dirty = src_metadata.extract_metadata(lib_file)
                assert meta_dirty is not None
                self.assertEqual(meta_dirty.dirty, "testing dirty")

                # Third mark-clean should clean the dirty node and clear the dirty tag
                ret3 = cleanroom_uv_runner.run_cleanroom_target(
                    target_str="//pkg/parts/sample:sample#lib",
                    action="mark-clean",
                    workspace_dir=tmp_dir,
                )
                self.assertEqual(ret3, 0)
                meta3 = src_metadata.extract_metadata(lib_file)
                assert meta3 is not None
                self.assertIsNone(meta3.dirty)
                single_clean_time = meta3.last_cleaned
                single_clean_mtime = os.path.getmtime(lib_file)

                # Single target mark-clean on clean target should NOT update the file
                ret4 = cleanroom_uv_runner.run_cleanroom_target(
                    target_str="//pkg/parts/sample:sample#lib",
                    action="mark-clean",
                    workspace_dir=tmp_dir,
                )
                self.assertEqual(ret4, 0)
                meta4 = src_metadata.extract_metadata(lib_file)
                assert meta4 is not None
                self.assertEqual(meta4.last_cleaned, single_clean_time)
                self.assertEqual(os.path.getmtime(lib_file), single_clean_mtime)

                # Single target mark dirty then mark-clean
                ret_single_dirty = cleanroom_uv_runner.run_cleanroom_target(
                    target_str="//pkg/parts/sample:sample#lib",
                    action="dirty",
                    message="testing single dirty",
                    workspace_dir=tmp_dir,
                )
                self.assertEqual(ret_single_dirty, 0)
                meta_s_dirty = src_metadata.extract_metadata(lib_file)
                assert meta_s_dirty is not None
                self.assertEqual(meta_s_dirty.dirty, "testing single dirty")

                ret5 = cleanroom_uv_runner.run_cleanroom_target(
                    target_str="//pkg/parts/sample:sample#lib",
                    action="mark-clean",
                    workspace_dir=tmp_dir,
                )
                self.assertEqual(ret5, 0)
                meta5 = src_metadata.extract_metadata(lib_file)
                assert meta5 is not None
                self.assertIsNone(meta5.dirty)
            finally:
                os.chdir(orig_cwd)


if __name__ == "__main__":
    unittest.main()
