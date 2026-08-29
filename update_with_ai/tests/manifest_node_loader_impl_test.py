"""
Tests for the ManifestNodeLoaderImpl implementation.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from lib.build_graph_storage import GraphConfig
from lib.manifest_node_loader_impl import (
    ManifestNodeLoaderImpl,
    _virtual_names,
)


class TestVirtualNames(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(_virtual_names([]), {})

    def test_single_element(self) -> None:
        self.assertEqual(_virtual_names(["a/b/c.txt"]), {"a/b/c.txt": "c.txt"})

    def test_no_collisions(self) -> None:
        paths = ["pkg1/a.txt", "pkg2/b.txt"]
        self.assertEqual(_virtual_names(paths), {"pkg1/a.txt": "a.txt", "pkg2/b.txt": "b.txt"})

    def test_collisions_disambiguated(self) -> None:
        paths = ["pkg1/sub/a.txt", "pkg2/sub/a.txt", "pkg3/other/a.txt"]
        v = _virtual_names(paths)
        self.assertEqual(v["pkg1/sub/a.txt"], "pkg1/sub/a.txt")
        self.assertEqual(v["pkg2/sub/a.txt"], "pkg2/sub/a.txt")
        self.assertEqual(v["pkg3/other/a.txt"], "other/a.txt")


class TestManifestNodeLoaderImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_root = os.path.join(self.temp_dir, "ws")
        os.makedirs(self.workspace_root, exist_ok=True)
        self.loader = ManifestNodeLoaderImpl()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_manifest(self, pkg_rel: str, filename: str, data: dict) -> str:
        pkg_path = os.path.join(self.workspace_root, pkg_rel)
        os.makedirs(pkg_path, exist_ok=True)
        full_path = os.path.join(pkg_path, filename)
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return full_path

    def test_basic_manifest_loading(self) -> None:
        self._write_manifest("pkg1", "target_manifest.json", {
            "label": "//pkg1:target",
            "prompt": "Test prompt 1",
            "src": "target.py",
            "silent_srcs": [],
            "deps": [],
            "silent_deps": [],
            "feedback_deps": [],
            "star_deps": [],
        })

        res = self.loader.resolve_graph(GraphConfig(workspace_root=self.workspace_root))
        self.assertIn("//pkg1:target", res.node_definitions)
        defn = res.node_definitions["//pkg1:target"]
        self.assertEqual(defn.prompt, "Test prompt 1")
        self.assertIn("target.py", defn.sandbox_config.file_mappings)
        self.assertEqual(res.package_directories["//pkg1:target"], os.path.join(self.workspace_root, "pkg1"))

    def test_star_dependency_closure(self) -> None:
        self._write_manifest("pkgA", "nodeA_manifest.json", {
            "label": "//pkgA:nodeA",
            "prompt": "Node A",
            "src": "a.py",
            "star_deps": ["//pkgB:nodeB"],
        })
        self._write_manifest("pkgB", "nodeB_manifest.json", {
            "label": "//pkgB:nodeB",
            "prompt": "Node B",
            "src": "b.py",
            "star_deps": ["//pkgC:nodeC"],
        })
        self._write_manifest("pkgC", "nodeC_manifest.json", {
            "label": "//pkgC:nodeC",
            "prompt": "Node C",
            "src": "c.py",
        })

        res = self.loader.resolve_graph(GraphConfig(workspace_root=self.workspace_root))
        defnA = res.node_definitions["//pkgA:nodeA"]
        # Node A should have read access to b.py and c.py via transitive star-deps!
        self.assertIn("b.py", defnA.sandbox_config.readable_paths)
        self.assertIn("c.py", defnA.sandbox_config.readable_paths)

    def test_feedback_deps_and_blame_targets(self) -> None:
        self._write_manifest("dep", "dep_manifest.json", {
            "label": "//dep:target",
            "prompt": "Dep prompt",
            "src": "dep.py",
        })
        self._write_manifest("consumer", "consumer_manifest.json", {
            "label": "//consumer:target",
            "prompt": "Consumer prompt",
            "src": "consumer.py",
            "feedback_deps": ["//dep:target"],
        })

        res = self.loader.resolve_graph(GraphConfig(workspace_root=self.workspace_root))
        consumer_defn = res.node_definitions["//consumer:target"]
        self.assertEqual(consumer_defn.sandbox_config.blame_targets.get("dep.py"), "//dep:target")

    def test_synthetic_manifest_for_missing_deps(self) -> None:
        self._write_manifest("pkg", "target_manifest.json", {
            "label": "//pkg:target",
            "prompt": "Prompt",
            "deps": ["//external:dep"],
        })

        res = self.loader.resolve_graph(GraphConfig(workspace_root=self.workspace_root))
        self.assertIn("//external:dep", res.node_definitions)
        self.assertEqual(res.node_dependencies["//pkg:target"], ["//external:dep"])


if __name__ == "__main__":
    unittest.main()
