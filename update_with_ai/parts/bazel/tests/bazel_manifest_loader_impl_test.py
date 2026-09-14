"""Unit tests for bazel_manifest_loader_impl aligned with grounding specifications."""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from typing import Dict, Optional, Set

from update_with_ai.parts.agent.lib.agent_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.bazel.lib.bazel_manifest_loader import (
    BazelManifestLoader,
    Manifest,
)
from update_with_ai.parts.bazel.lib.bazel_manifest_loader_impl import (
    BazelManifestLoader as BazelManifestLoaderImpl,
    __initialize__,
)
from update_with_ai.parts.bazel.lib.bazel_target import BazelTarget, NodeDirectory
from update_with_ai.parts.dag.lib.dag_storage import Dependency, Message, Node
from support.lib.lifecycle import LifecycleRegistry, enter_phase


def _make_node_dir(path: str) -> NodeDirectory:
    obj = object.__new__(NodeDirectory)
    object.__setattr__(obj, "path", path)
    return obj


class MockNodeIdUtils:
    tier = "system"

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir

    def _norm(self, s: str) -> str:
        s = s.strip()
        if not s:
            return ""
        if not s.startswith("//"):
            s = f"//{s}"
        if ":" not in s:
            parts = s[2:].split("/")
            s = f"{s}:{parts[-1]}"
        return s

    def normalize(self, raw_label: str, role_label: str = "") -> Node:
        if "#" in raw_label:
            u, r = raw_label.split("#", 1)
            return Node(unit_address=self._norm(u), role_address=self._norm(r))
        return Node(
            unit_address=self._norm(raw_label),
            role_address=self._norm(role_label) if role_label else "",
        )

    def extract_directory(self, node: Node) -> NodeDirectory:
        pkg = node.unit_address.split(":")[0].lstrip("/")
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
            self.node_utils, keys=[BazelTarget], tier="system"
        )
        self.registry.register_instance(
            self.storage, keys=[AgentStorage], tier="system"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_manifest(self) -> None:
        """CUJ: Reading manifest file from node package directory."""
        node = Node(unit_address="//pkg/sub:target", role_address="")
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
            with open(
                os.path.join(rf_main, "rf_node_manifest.json"), "w", encoding="utf-8"
            ) as f:
                f.write('{"label": "//pkg/rf:rf_node"}')
            rf_node = Node(unit_address="//pkg/rf:rf_node", role_address="")
            with patch.dict(os.environ, {"RUNFILES_DIR": runfiles_dir}):
                # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
                # Requirement: [BazelManifestLoader] The bazel manifest loader retrieves the manifest for a node in dag storage.
                rf_manifest = loader.get_manifest(rf_node)
                self.assertIsNotNone(rf_manifest)
                assert rf_manifest is not None
                self.assertIn("rf_node", rf_manifest)

            # Candidate read failure suppresses OSError
            err_node = Node(unit_address="//pkg/err:err_node", role_address="")
            err_pkg = os.path.join(self.test_dir, "pkg/err")
            os.makedirs(err_pkg, exist_ok=True)
            with open(
                os.path.join(err_pkg, ".manifest.json"), "w", encoding="utf-8"
            ) as f:
                f.write('{"label": "//pkg/err:err_node"}')
            with patch("builtins.open", side_effect=OSError("Read error")):
                # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
                self.assertIsNone(loader.get_manifest(err_node))

    def test_get_manifest_synthesizes_from_unit_and_role(self) -> None:
        """CUJ: get_manifest synthesizes node manifest with template, parameters, and 2D dependencies."""
        unit_node = Node(unit_address="//pkg/calc:calc_impl", role_address="//rules:qa")
        calc_pkg = os.path.join(self.test_dir, "pkg/calc")
        rules_pkg = os.path.join(self.test_dir, "rules")
        os.makedirs(calc_pkg, exist_ok=True)
        os.makedirs(rules_pkg, exist_ok=True)

        with open(
            os.path.join(calc_pkg, ".calc_impl_unit_manifest.json"),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                {
                    "label": "//pkg/calc:calc_impl",
                    "name": "calc_impl",
                    "dir": "pkg/calc",
                    "unit_deps": ["//pkg/calc:calc_spec"],
                    "component_type": "implementation",
                },
                f,
            )

        with open(
            os.path.join(rules_pkg, ".qa_role_manifest.json"),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                {
                    "label": "//rules:qa",
                    "name": "qa",
                    "src_pattern": "{unit_dir}/logs/{unit_name}_qa.log",
                    "template": "//templates:empty",
                    "prompt_template": "Verify {unit_name}",
                    "role_deps": [":test"],
                    "feedback_role_deps": [":lib"],
                    "silent_role_deps": [":high"],
                    "star_role_deps": [":low"],
                    "silent_cross_role_deps": [":lib"],
                    "active_component_types": ["implementation"],
                },
                f,
            )

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: A manifest loader synthesizes target node manifests with templates, template parameters, declared dependencies, feedback dependencies, silent dependencies, and star dependencies across unit and role dimensions.
            raw_manifest = loader.get_manifest(unit_node)
            self.assertIsNotNone(raw_manifest)
            assert raw_manifest is not None
            data = json.loads(raw_manifest)

            self.assertEqual(data["unit"], "//pkg/calc:calc_impl")
            self.assertEqual(data["role"], "//rules:qa")
            self.assertEqual(data["template"], "//templates:empty")
            self.assertEqual(data["template_parameters"]["unit_name"], "calc_impl")
            self.assertEqual(data["template_parameters"]["unit_dir"], "pkg/calc")
            self.assertIn("//pkg/calc:calc_impl#//rules:test", data["deps"])
            self.assertIn("//pkg/calc:calc_impl#//rules:lib", data["feedback_deps"])
            self.assertIn("//pkg/calc:calc_impl#//rules:high", data["silent_deps"])
            self.assertIn("//pkg/calc:calc_spec#//rules:low", data["star_deps"])
            self.assertIn("//pkg/calc:calc_spec#//rules:lib", data["silent_deps"])

            # Inactive component type (pass-through node)
            asm_node = Node(unit_address="//pkg/calc:calc_asm", role_address="//rules:qa")
            with open(
                os.path.join(calc_pkg, ".calc_asm_unit_manifest.json"),
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    {
                        "label": "//pkg/calc:calc_asm",
                        "name": "calc_asm",
                        "dir": "pkg/calc",
                        "unit_deps": ["//pkg/calc:calc_impl"],
                        "component_type": "assembly",
                    },
                    f,
                )

            asm_manifest = loader.get_manifest(asm_node)
            self.assertIsNotNone(asm_manifest)
            assert asm_manifest is not None
            asm_data = json.loads(asm_manifest)
            self.assertEqual(asm_data["src"], "")
            self.assertEqual(asm_data["verify"], "")
            self.assertIn("//pkg/calc:calc_impl#//rules:qa", asm_data["deps"])
            self.assertIn("//pkg/calc:calc_asm#//rules:test", asm_data["deps"])

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
            self.assertEqual(
                defn.node, Node(unit_address="//pkg:target_a", role_address="")
            )
            self.assertEqual(defn.task_prompt, "Clean target A")

            # Definitions recorded in storage
            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using a node identifier utility, populating the agent storage.
            self.assertEqual(self.storage.get_node_definition(defn.node), defn)

            # Dependencies recorded in storage
            deps = self.storage.get_dependencies(defn.node)
            self.assertEqual(len(deps), 2)
            dep_b = next(d for d in deps if d.node.unit_address == "//pkg:dep_b")
            silent_c = next(d for d in deps if d.node.unit_address == "//pkg:silent_c")

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
            self.assertEqual(
                defn.node, Node(unit_address="//pkg:sample_node", role_address="")
            )
            self.assertEqual(defn.task_prompt, "Implement the requested feature")

            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using a node identifier utility, populating the agent storage.
            self.assertEqual(self.storage.get_node_definition(defn.node), defn)

            # Dependencies recorded in storage
            deps = self.storage.get_dependencies(defn.node)
            self.assertEqual(len(deps), 2)
            dep_x = next(d for d in deps if d.node.unit_address == "//pkg:dep_x")
            silent_y = next(d for d in deps if d.node.unit_address == "//pkg:silent_y")
            self.assertFalse(dep_x.is_silent)
            self.assertTrue(silent_y.is_silent)

            # Source files recorded in storage
            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations using a node identifier utility, populating the agent storage.
            self.assertIn(defn.node, self.storage._source_files)
            self.assertEqual(
                self.storage._source_files[defn.node],
                os.path.normpath(os.path.join(self.test_dir, "pkg/src.txt")),
            )

    def test_load_manifest_from_unit_and_role_manifests(self) -> None:
        """CUJ: Loading synthesized manifest from unit and role manifests."""
        synthesized_data = {
            "unit": "//parts/sample:sample_impl",
            "role": "//update_python_with_ai/roles:lib",
            "unit_data": {
                "label": "//parts/sample:sample_impl",
                "name": "sample_impl",
                "dir": "parts/sample",
                "unit_deps": ["//parts/sample:sample_spec"],
                "component_type": "implementation",
            },
            "role_data": {
                "label": "//update_python_with_ai/roles:lib",
                "name": "lib",
                "src_pattern": "{unit_dir}/lib/{unit_name}.py",
                "prompt_template": "Align {unit_name} per guide. {lib_kind_clause}",
                "role_deps": [":low"],
                "star_role_deps": [":low"],
                "silent_cross_role_deps": [":lib"],
            },
        }
        manifest_content = Manifest(json.dumps(synthesized_data))

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            results = loader.load_manifest(manifest_content, self.storage)

            # Requirement: A manifest loader resolves target manifests by loading unit manifests and role manifests to synthesize node definitions and dependencies across unit and role dimensions.
            self.assertEqual(len(results), 1)
            defn = results[0]
            expected_node = Node(
                unit_address="//parts/sample:sample_impl",
                role_address="//update_python_with_ai/roles:lib",
            )
            self.assertEqual(defn.node, expected_node)

            # Requirement: A manifest loader evaluates role source patterns and task prompt templates parameterized with unit metadata to configure synthesized nodes.
            self.assertIn("Align sample_impl per guide.", str(defn.task_prompt))
            self.assertIn("implementation module", str(defn.task_prompt))

            self.assertIn(expected_node, self.storage._source_files)
            self.assertEqual(
                self.storage._source_files[expected_node],
                os.path.normpath("parts/sample/lib/sample_impl.py"),
            )

            # 2D dependencies checked
            deps = self.storage.get_dependencies(expected_node)
            # Intra-unit role dep on :low
            low_dep = next(
                d
                for d in deps
                if d.node.unit_address == "//parts/sample:sample_impl"
                and ":low" in d.node.role_address
            )
            self.assertFalse(low_dep.is_silent)

            # Cross-unit star dep on sample_spec:low
            cross_low = next(
                d
                for d in deps
                if d.node.unit_address == "//parts/sample:sample_spec"
                and ":low" in d.node.role_address
            )
            self.assertFalse(cross_low.is_silent)

            # Cross-unit silent dep on sample_spec:lib
            cross_lib = next(
                d
                for d in deps
                if d.node.unit_address == "//parts/sample:sample_spec"
                and ":lib" in d.node.role_address
            )
            self.assertTrue(cross_lib.is_silent)

    def test_load_manifest_for_inactive_role_creates_passthrough_node(self) -> None:
        """CUJ: Inactive roles produce promptless pass-through nodes with unit and role dependencies."""
        passthrough_data = {
            "unit": "//parts/sample:sample_asm",
            "role": "//update_python_with_ai/roles:qa",
            "unit_data": {
                "label": "//parts/sample:sample_asm",
                "name": "sample_asm",
                "dir": "parts/sample",
                "unit_deps": ["//parts/sample:dep_impl"],
                "component_type": "assembly",
            },
            "role_data": {
                "label": "//update_python_with_ai/roles:qa",
                "name": "qa",
                "src_pattern": "{unit_dir}/logs/{unit_name}_qa.log",
                "prompt_template": "Run QA for {unit_name}",
                "role_deps": [":lib"],
                "active_component_types": ["implementation"],
            },
        }
        manifest_content = Manifest(json.dumps(passthrough_data))

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: A manifest loader synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.
            results = loader.load_manifest(manifest_content, self.storage)

            self.assertEqual(len(results), 1)
            defn = results[0]
            expected_node = Node(
                unit_address="//parts/sample:sample_asm",
                role_address="//update_python_with_ai/roles:qa",
            )
            self.assertEqual(defn.node, expected_node)
            self.assertEqual(defn.task_prompt, "")

            # No source file registered for pass-through node
            self.assertNotIn(expected_node, self.storage._source_files)

            # Dependencies include cross-unit (dep_impl, qa) and intra-unit (sample_asm, lib)
            deps = self.storage.get_dependencies(expected_node)
            self.assertEqual(len(deps), 2)
            cross_qa = next(
                d
                for d in deps
                if d.node.unit_address == "//parts/sample:dep_impl"
                and ":qa" in d.node.role_address
            )
            self.assertFalse(cross_qa.is_silent)

            intra_lib = next(
                d
                for d in deps
                if d.node.unit_address == "//parts/sample:sample_asm"
                and ":lib" in d.node.role_address
            )
            self.assertFalse(intra_lib.is_silent)


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
