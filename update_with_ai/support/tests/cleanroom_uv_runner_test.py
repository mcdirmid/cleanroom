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

from support.lib.lifecycle import get_singleton
from update_with_ai.parts.systems.lib import uv_cleanroom_asm
from update_with_ai.parts.uv.lib import uv_manifest_loader
from update_with_ai.support.lib import cleanroom_uv_runner


class CleanroomUvRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        uv_cleanroom_asm.__initialize__()
        cls.loader = get_singleton(uv_manifest_loader.UvManifestLoader)
        cls.repo_root = _repo_root

    def test_resolve_scope_entire_scope(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            "staging", self.repo_root, self.loader
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
            "staging/parts/sandbox", self.repo_root, self.loader
        )
        self.assertIsNotNone(nodes)
        assert nodes is not None
        self.assertEqual(len(nodes), 111)
        for n in nodes:
            self.assertTrue(n.unit_address.startswith("//staging/parts/sandbox:"))

    def test_resolve_scope_part_role(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            "staging/parts/sandbox/lib", self.repo_root, self.loader
        )
        self.assertIsNotNone(nodes)
        assert nodes is not None
        self.assertEqual(len(nodes), 15)
        for n in nodes:
            self.assertTrue(n.unit_address.startswith("//staging/parts/sandbox:"))
            self.assertEqual(n.role_address, "lib")

    def test_resolve_scope_single_file(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            "staging/parts/sandbox/lib/sandbox_file_reader_impl.py",
            self.repo_root,
            self.loader,
        )
        self.assertIsNotNone(nodes)
        assert nodes is not None
        self.assertEqual(len(nodes), 1)
        self.assertEqual(
            nodes[0].unit_address, "//staging/parts/sandbox:sandbox_file_reader_impl"
        )
        self.assertEqual(nodes[0].role_address, "lib")

    def test_resolve_scope_label_target_returns_none(self) -> None:
        nodes = cleanroom_uv_runner.resolve_scope_nodes(
            "//staging/parts/systems:cleanroom_asm#coverage",
            self.repo_root,
            self.loader,
        )
        self.assertIsNone(nodes)

    def test_run_cleanroom_target_mark_clean_scope(self) -> None:
        ret = cleanroom_uv_runner.run_cleanroom_target(
            target_str="staging/parts/sandbox/lib",
            action="mark-clean",
        )
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
