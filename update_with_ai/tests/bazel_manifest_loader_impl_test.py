"""Unit tests for bazel_manifest_loader_impl aligned with grounding specifications."""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from typing import Dict, Optional, Set

from lib.agent_storage import AgentStorage, NodeDefinition, TaskPrompt
from lib.bazel_manifest_loader import BazelManifestLoader, Manifest
from lib.bazel_manifest_loader_impl import (
    BazelManifestLoader as BazelManifestLoaderImpl,
    __initialize__,
)
from lib.bazel_node_id_utils import BazelNodeIdentifierUtility, NodeDirectory
from lib.dag_storage import Dependency, Message, Node
from support.lib.lifecycle import LifecycleRegistry, enter_phase


def _make_node_dir(path: str) -> NodeDirectory:
    obj = object.__new__(NodeDirectory)
    object.__setattr__(obj, "path", path)
    return obj


class MockNodeIdUtils:
    tier = "system"

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir

    def normalize(self, raw_label: str) -> Node:
        s = raw_label.strip()
        if not s.startswith("//"):
            s = f"//{s}"
        if ":" not in s:
            parts = s[2:].split("/")
            s = f"{s}:{parts[-1]}"
        return Node(address=s)

    def extract_directory(self, node: Node) -> NodeDirectory:
        pkg = node.address.split(":")[0].lstrip("/")
        return _make_node_dir(os.path.join(self.base_dir, pkg))


class MockGraphStorage:
    tier = "system"

    def __init__(self) -> None:
        self._definitions: Dict[Node, NodeDefinition] = {}
        self._dependencies: Dict[Node, Set[Dependency]] = {}
        self._source_files: Dict[Node, str] = {}

    def get_node_definition(self, node: Node) -> Optional[NodeDefinition]:
        return self._definitions.get(node)

    def get_dependencies(self, node: Node) -> Set[Dependency]:
        return set(self._dependencies.get(node, set()))

    def get_dependents(self, node: Node) -> Set[Node]:
        return set()

    def get_messages(self, node: Node) -> Set[Message]:
        return set()

    def is_dirty(self, node: Node) -> bool:
        return False

    def register_dependent(self, node: Node) -> None:
        pass

    def clear_dependents(self, node: Node) -> None:
        pass

    def add_message(self, message: Message, to: Node) -> None:
        pass

    def clear_messages(self, node: Node) -> None:
        pass


class BazelManifestLoaderImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.node_utils = MockNodeIdUtils(self.test_dir)
        self.storage = MockGraphStorage()

        self.registry.register_instance(
            self.node_utils, keys=[BazelNodeIdentifierUtility], tier="system"
        )
        self.registry.register_instance(self.storage, keys=[AgentStorage], tier="system")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_manifest(self) -> None:
        """CUJ: Reading manifest file from node package directory."""
        node = Node(address="//pkg/sub:target")
        pkg_path = os.path.join(self.test_dir, "pkg/sub")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file = os.path.join(pkg_path, ".manifest.json")

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)

            # Missing manifest returns None
            # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
            self.assertIsNone(loader.get_manifest(node))

            # Existing manifest returns content
            with open(manifest_file, "w", encoding="utf-8") as f:
                f.write('{"label": "//pkg/sub:target"}')

            # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
            # Requirement: [BazelManifestLoader] The bazel manifest loader retrieves the manifest for a node in dag storage.
            manifest = loader.get_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertIn("pkg/sub:target", manifest)

            # In-memory cache hit returns cached instance
            cached_manifest = loader.get_manifest(node)
            self.assertIs(cached_manifest, manifest)

            # Candidate path resolution through runfiles directory
            runfiles_dir = os.path.join(self.test_dir, "runfiles")
            rf_main = os.path.join(runfiles_dir, "_main")
            os.makedirs(rf_main, exist_ok=True)
            with open(os.path.join(rf_main, "rf_node_manifest.json"), "w", encoding="utf-8") as f:
                f.write('{"label": "//pkg/rf:rf_node"}')
            rf_node = Node(address="//pkg/rf:rf_node")
            with patch.dict(os.environ, {"RUNFILES_DIR": runfiles_dir}):
                # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
                # Requirement: [BazelManifestLoader] The bazel manifest loader retrieves the manifest for a node in dag storage.
                rf_manifest = loader.get_manifest(rf_node)
                self.assertIsNotNone(rf_manifest)
                assert rf_manifest is not None
                self.assertIn("rf_node", rf_manifest)

            # Candidate read failure suppresses OSError
            err_node = Node(address="//pkg/err:err_node")
            err_pkg = os.path.join(self.test_dir, "pkg/err")
            os.makedirs(err_pkg, exist_ok=True)
            with open(os.path.join(err_pkg, ".manifest.json"), "w", encoding="utf-8") as f:
                f.write('{"label": "//pkg/err:err_node"}')
            with patch("builtins.open", side_effect=OSError("Read error")):
                # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
                self.assertIsNone(loader.get_manifest(err_node))

    def test_load_manifest_normalizes_labels_and_registers_deps(self) -> None:
        """CUJ: Loading manifest resolves targets, sets definitions, and records silent/non-silent deps."""
        manifest_data = {
            "targets": [
                {
                    "label": "//pkg:target_a",
                    "task_prompt": "Clean target A",
                    "deps": ["//pkg:dep_b"],
                    "silent_deps": ["//pkg:silent_c"],
                }
            ]
        }
        manifest_content = Manifest(json.dumps(manifest_data))

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            results = loader.load_manifest(manifest_content, self.storage)

            # Requirement: A manifest loader parses JSON manifests using the filesystem into json manifest records.
            self.assertEqual(len(results), 1)
            defn = results[0]
            # Requirement: A manifest loader normalizes node references into canonical nodes using node identifier utilities.
            self.assertEqual(defn.node, Node(address="//pkg:target_a"))
            self.assertEqual(defn.task_prompt, "Clean target A")

            # Definitions recorded in storage
            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using a node identifier utility, populating the bazel graph storage.
            self.assertEqual(self.storage.get_node_definition(defn.node), defn)

            # Dependencies recorded in storage
            deps = self.storage.get_dependencies(defn.node)
            self.assertEqual(len(deps), 2)
            dep_b = next(d for d in deps if d.node.address == "//pkg:dep_b")
            silent_c = next(d for d in deps if d.node.address == "//pkg:silent_c")

            # Requirement: A manifest loader registers silent dependencies as non-propagating dependencies excluding their source files.
            self.assertFalse(dep_b.is_silent)
            self.assertTrue(silent_c.is_silent)

    def test_load_manifest_from_update_with_ai_schema(self) -> None:
        """CUJ: Loading top-level manifest object directly formatted by update_with_ai.bzl."""
        manifest_data = {
            "label": "//pkg:sample_node",
            "name": "sample_node",
            "prompt": "Implement the requested feature",
            "tools": [":tool_a"],
            "deps": ["//pkg:dep_x"],
            "silent_deps": ["//pkg:silent_y"],
            "feedback_deps": [],
            "star_deps": [],
            "src": "src.txt",
            "template": None,
            "guide": None,
            "silent_srcs": [],
            "verify": None,
            "dependency_paths": [],
        }
        manifest_content = Manifest(json.dumps(manifest_data))

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            results = loader.load_manifest(manifest_content, self.storage)

            # Requirement: A manifest loader parses JSON manifests using the filesystem into json manifest records.
            self.assertEqual(len(results), 1)
            defn = results[0]
            # Requirement: A manifest loader normalizes node references into canonical nodes using node identifier utilities.
            self.assertEqual(defn.node, Node(address="//pkg:sample_node"))
            self.assertEqual(defn.task_prompt, "Implement the requested feature")

            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using a node identifier utility, populating the bazel graph storage.
            self.assertEqual(self.storage.get_node_definition(defn.node), defn)

            # Dependencies recorded in storage
            deps = self.storage.get_dependencies(defn.node)
            self.assertEqual(len(deps), 2)
            dep_x = next(d for d in deps if d.node.address == "//pkg:dep_x")
            silent_y = next(d for d in deps if d.node.address == "//pkg:silent_y")
            self.assertFalse(dep_x.is_silent)
            self.assertTrue(silent_y.is_silent)

            # Source files recorded in storage
            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using a node identifier utility, populating the bazel graph storage.
            self.assertIn(defn.node, self.storage._source_files)
            self.assertEqual(
                self.storage._source_files[defn.node],
                os.path.normpath(os.path.join(self.test_dir, "pkg/src.txt")),
            )


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - A manifest loader resolves package-relative file paths against target package directories.
# - A manifest loader maps declared source files, templates, and silent source files into read-write files and template entries.
# - A manifest loader expands direct dependencies and star dependencies into read-only files.
# - A manifest loader resolves guide targets into task guides and feedback dependencies into blame targets.
# - A manifest loader derives file aliases for all accessible workspace files.
# - A manifest loader synthesizes node definitions for referenced dependency targets lacking manifests.
# - [BazelManifestLoader] A manifest loader resolves declared source files and templates into read-write files and templates in node configurations.
# - [BazelManifestLoader] A manifest loader resolves declared silent source files into read-write files while excluding them from dependent read-only files.
# - [BazelManifestLoader] A manifest loader resolves declared direct dependencies into read-only files, and star dependencies into transitive read-only file closures.
# - [BazelManifestLoader] A manifest loader resolves declared silent dependencies as non-propagating dependencies while excluding their source files from read-only files.
# - [BazelManifestLoader] A manifest loader resolves declared guide targets into task guides in node configurations.
# - [BazelManifestLoader] A manifest loader resolves declared feedback dependencies into blame targets mapped to their owning dependency nodes in node configurations.
# - [BazelManifestLoader] A manifest loader generates node configurations with minimally disambiguated file aliases.
# - [BazelManifestLoader] A manifest loader synthesizes definitions for declared dependencies lacking explicit manifests.

