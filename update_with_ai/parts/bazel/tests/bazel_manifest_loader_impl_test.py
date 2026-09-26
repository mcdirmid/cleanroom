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
        TargetManifest,
)
from update_with_ai.parts.bazel.lib.bazel_manifest_loader_impl import (
    BazelManifestLoader as BazelManifestLoaderImpl,
    __initialize__,
)
from update_with_ai.parts.bazel.lib.bazel_target import BazelTarget, NodeDirectory
from update_with_ai.parts.dag.lib.dag_storage import DagDependency, DagMessage, DagNode
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

    def normalize(self, raw_label: str, role_label: str = "") -> DagNode:
        if "#" in raw_label:
            u, r = raw_label.split("#", 1)
            return DagNode(unit_address=self._norm(u), role_address=self._norm(r))
        return DagNode(
            unit_address=self._norm(raw_label),
            role_address=self._norm(role_label) if role_label else "",
        )

    def extract_directory(self, node: DagNode) -> NodeDirectory:
        pkg = node.unit_address.split(":")[0].lstrip("/")
        return _make_node_dir(os.path.join(self.base_dir, pkg))


class MockGraphStorage:
    tier = "system"

    def __init__(self) -> None:
        self._definitions: Dict[DagNode, NodeDefinition] = {}
        self._dependencies: Dict[DagNode, Set[DagDependency]] = {}
        self._source_files: Dict[DagNode, str] = {}

    def get_node_definition(self, node: DagNode) -> Optional[NodeDefinition]:
        return self._definitions.get(node)

    def get_dependencies(self, node: DagNode) -> Set[DagDependency]:
        return set(self._dependencies.get(node, set()))

    def get_dependents(self, node: DagNode) -> Set[DagNode]:
        return set()

    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        return set()

    def is_dirty(self, node: DagNode) -> bool:
        return False

    def register_dependent(self, node: DagNode) -> None:
        pass

    def clear_dependents(self, node: DagNode) -> None:
        pass

    def add_message(self, message: DagMessage, to: DagNode) -> None:
        pass

    def clear_messages(self, node: DagNode) -> None:
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
        node = DagNode(unit_address="//pkg/sub:target", role_address="")
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
            rf_node = DagNode(unit_address="//pkg/rf:rf_node", role_address="")
            with patch.dict(os.environ, {"RUNFILES_DIR": runfiles_dir}):
                # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
                # Requirement: [BazelManifestLoader] The bazel manifest loader retrieves the manifest for a node in dag storage.
                rf_manifest = loader.get_manifest(rf_node)
                self.assertIsNotNone(rf_manifest)
                assert rf_manifest is not None
                self.assertIn("rf_node", rf_manifest)

            # Candidate read failure suppresses OSError
            err_node = DagNode(unit_address="//pkg/err:err_node", role_address="")
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
        unit_node = DagNode(unit_address="//pkg/calc:calc_impl", role_address="//rules:qa")
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
            asm_node = DagNode(
                unit_address="//pkg/calc:calc_asm", role_address="//rules:qa"
            )
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
        manifest_content = TargetManifest(json.dumps(manifest_data))

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            results = loader.load_manifest(manifest_content, self.storage)

            # Requirement: A manifest loader parses JSON manifests using the filesystem into json manifest records.
            self.assertEqual(len(results), 1)
            defn = results[0]
            # Requirement: A manifest loader normalizes node references into canonical nodes.
            self.assertEqual(
                defn.node, DagNode(unit_address="//pkg:target_a", role_address="")
            )
            self.assertEqual(defn.task_prompt, "Clean target A")

            # Definitions recorded in storage
            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations, populating the agent storage.
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
        manifest_content = TargetManifest(json.dumps(manifest_data))

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            results = loader.load_manifest(manifest_content, self.storage)

            # Requirement: A manifest loader parses JSON manifests using the filesystem into json manifest records.
            self.assertEqual(len(results), 1)
            defn = results[0]
            # Requirement: A manifest loader normalizes node references into canonical nodes.
            self.assertEqual(
                defn.node, DagNode(unit_address="//pkg:sample_node", role_address="")
            )
            self.assertEqual(defn.task_prompt, "Implement the requested feature")

            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations, populating the agent storage.
            self.assertEqual(self.storage.get_node_definition(defn.node), defn)

            # Dependencies recorded in storage
            deps = self.storage.get_dependencies(defn.node)
            self.assertEqual(len(deps), 2)
            dep_x = next(d for d in deps if d.node.unit_address == "//pkg:dep_x")
            silent_y = next(d for d in deps if d.node.unit_address == "//pkg:silent_y")
            self.assertFalse(dep_x.is_silent)
            self.assertTrue(silent_y.is_silent)

            # Source files recorded in storage
            # Requirement: [BazelManifestLoader] A manifest loader resolves manifests into target nodes, dependencies, node definitions, task prompts, and node configurations, populating the agent storage.
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
        manifest_content = TargetManifest(json.dumps(synthesized_data))

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            results = loader.load_manifest(manifest_content, self.storage)

            # Requirement: A manifest loader resolves target manifests by loading unit manifests and role manifests to synthesize node definitions and dependencies across unit and role dimensions.
            self.assertEqual(len(results), 1)
            defn = results[0]
            expected_node = DagNode(
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
        manifest_content = TargetManifest(json.dumps(passthrough_data))

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: A manifest loader synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.
            results = loader.load_manifest(manifest_content, self.storage)

            self.assertEqual(len(results), 1)
            defn = results[0]
            expected_node = DagNode(
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

    def test_get_manifest_direct_file_and_alternative_filenames(self) -> None:
        """CUJ: get_manifest handles direct node manifest files, fallback filenames, and address without colon."""
        pkg_path = os.path.join(self.test_dir, "pkg/direct")
        role_pkg_path = os.path.join(self.test_dir, "update_python_with_ai/roles")
        os.makedirs(pkg_path, exist_ok=True)
        os.makedirs(role_pkg_path, exist_ok=True)

        node_direct = DagNode(unit_address="//pkg/direct:myunit", role_address="//update_python_with_ai/roles:myrole")
        direct_file = os.path.join(pkg_path, "myunit_myrole_manifest.json")
        direct_content = {
            "unit_data": {"name": "myunit"},
            "role_data": {"name": "myrole"},
        }
        with open(direct_file, "w", encoding="utf-8") as f:
            json.dump(direct_content, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
            # Requirement: [BazelManifestLoader] The bazel manifest loader retrieves the manifest for a node in dag storage.
            m = loader.get_manifest(node_direct)
            self.assertIsNotNone(m)
            assert m is not None
            self.assertIn("myunit", m)

        # 2. Alternative filenames: {unit_name}_manifest.json and {role_name}_manifest.json with no-colon addresses
        pkg_alt = os.path.join(self.test_dir, "alt")
        role_pkg_no_colon = os.path.join(self.test_dir, "altrole")
        os.makedirs(pkg_alt, exist_ok=True)
        os.makedirs(role_pkg_no_colon, exist_ok=True)
        unit_alt_file = os.path.join(pkg_alt, "altunit_manifest.json")
        role_alt_file = os.path.join(role_pkg_no_colon, "altrole_manifest.json")

        with open(unit_alt_file, "w", encoding="utf-8") as f:
            json.dump({"unit_name": "altunit", "unit_dir": "alt", "deps": ["//ext_pkg:foo_ext"]}, f)
        with open(role_alt_file, "w", encoding="utf-8") as f:
            json.dump({
                "name": "altrole",
                "role_deps": ["//custom/roles:deprole"],
                "silent_cross_role_deps": [":lib"],
                "guide": "//docs:guide",
                "active_component_types": ["implementation"],
            }, f)

        node_no_colon = DagNode(unit_address="//alt:altunit", role_address="altrole")
        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
            m_alt = loader.get_manifest(node_no_colon)
            self.assertIsNotNone(m_alt)
            assert m_alt is not None
            parsed = json.loads(str(m_alt))
            self.assertIn("//docs:guide", parsed.get("deps", []))

        # 3. Leading dot fallback filenames and address without colon
        pkg_dot = os.path.join(self.test_dir, "dotpkg/dotunit")
        role_pkg_dot = os.path.join(self.test_dir, "dotrole")
        os.makedirs(pkg_dot, exist_ok=True)
        os.makedirs(role_pkg_dot, exist_ok=True)

        with open(os.path.join(pkg_dot, ".dotunit_manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"component_type": "implementation"}, f)
        with open(os.path.join(role_pkg_dot, ".dotrole_manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"active_component_types": ["implementation"]}, f)

        node_dot = DagNode(unit_address="dotpkg/dotunit", role_address="dotrole")
        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: The bazel manifest loader retrieves target manifests from workspace directories or runfiles trees for nodes in dag storage.
            m_dot = loader.get_manifest(node_dot)
            self.assertIsNotNone(m_dot)
            assert m_dot is not None
            parsed_dot = json.loads(str(m_dot))
            self.assertEqual(parsed_dot["unit"], "dotpkg/dotunit")

    def test_load_manifest_metadata_fallbacks_and_interface_clause(self) -> None:
        """CUJ: load_manifest handles label fallbacks, interface clauses, and no-colon role addresses."""
        manifest_data = {
            "unit_data": {
                "label": "//parts/sample:sample_iface",
                "unit_name": "sample_iface",
                "unit_dir": "parts/sample",
                "component_type": "interface",
            },
            "role_data": {
                "label": "ifacerole",
                "prompt_template": "Interface for {unit_name}",
                "role_deps": ["//custom/roles:deprole"],
                "active_component_types": ["interface"],
            },
        }
        manifest_content = TargetManifest(json.dumps(manifest_data))

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: A manifest loader resolves target manifests by loading unit manifests and role manifests to synthesize node definitions and dependencies across unit and role dimensions.
            # Requirement: A manifest loader evaluates role source patterns and task prompt templates parameterized with unit metadata to configure synthesized nodes.
            results = loader.load_manifest(manifest_content, self.storage)
            self.assertEqual(len(results), 1)
            defn = results[0]
            self.assertIn("Interface for sample_iface", defn.task_prompt)

        # 2. Data with role having no colon and unit_data missing name and dir
        manifest_nocolon = {
            "role": "simple_role",
            "unit_data": {
                "label": "//parts/sample:sample_unnamed",
                "component_type": "interface",
            },
            "role_data": {
                "label": "simple_role",
                "prompt_template": "Prompt",
                "active_component_types": ["interface"],
            },
        }
        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: A manifest loader resolves target manifests by loading unit manifests and role manifests to synthesize node definitions and dependencies across unit and role dimensions.
            res = loader.load_manifest(TargetManifest(json.dumps(manifest_nocolon)), self.storage)
            self.assertEqual(len(res), 1)

    def test_load_manifest_passthrough_and_active_additional_deps(self) -> None:
        """CUJ: load_manifest handles feedback, star, and silent dependencies in passthrough and active nodes."""
        # 1. Passthrough node with feedback_role_deps, star_role_deps, silent_role_deps
        passthrough_data = {
            "unit": "//parts/sample:sample_passthru",
            "role": "//update_python_with_ai/roles:test",
            "unit_data": {
                "label": "//parts/sample:sample_passthru",
                "name": "sample_passthru",
                "dir": "parts/sample",
                "component_type": "assembly",
            },
            "role_data": {
                "label": "//update_python_with_ai/roles:test",
                "feedback_role_deps": [":qa"],
                "star_role_deps": [":lib"],
                "silent_role_deps": [":silent_role"],
                "active_component_types": ["implementation"],
            },
        }
        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: A manifest loader synthesizes promptless pass-through node definitions that act as graph dependencies without propagating changes when a unit's component type is not active for a role.
            res_pt = loader.load_manifest(TargetManifest(json.dumps(passthrough_data)), self.storage)
            self.assertEqual(len(res_pt), 1)
            pt_node = res_pt[0].node
            deps_pt = self.storage.get_dependencies(pt_node)
            silent_deps = [d for d in deps_pt if d.is_silent]
            self.assertTrue(any(":silent_role" in d.node.role_address for d in silent_deps))

        # 2. Active node with feedback_role_deps, star_role_deps, silent_role_deps, and silent_cross_role_deps
        active_data = {
            "unit": "//parts/sample:sample_act",
            "role": "//update_python_with_ai/roles:lib",
            "unit_data": {
                "label": "//parts/sample:sample_act",
                "name": "sample_act",
                "dir": "parts/sample",
                "component_type": "implementation",
                "unit_deps": ["//parts/ext:tool_ext"],
            },
            "role_data": {
                "label": "//update_python_with_ai/roles:lib",
                "feedback_role_deps": [":feedback_role"],
                "star_role_deps": [":star_role"],
                "silent_role_deps": [":silent_role"],
                "silent_cross_role_deps": [":lib"],
                "active_component_types": ["implementation"],
            },
        }
        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: A manifest loader resolves target manifests by loading unit manifests and role manifests to synthesize node definitions and dependencies across unit and role dimensions.
            # Requirement: A manifest loader registers silent dependencies as non-propagating dependencies excluding their source files.
            res_act = loader.load_manifest(TargetManifest(json.dumps(active_data)), self.storage)
            self.assertEqual(len(res_act), 1)
            act_node = res_act[0].node
            deps_act = self.storage.get_dependencies(act_node)
            silent_act_deps = [d for d in deps_act if d.is_silent]
            self.assertTrue(any(":silent_role" in d.node.role_address for d in silent_act_deps))


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
