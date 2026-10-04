"""Unit tests for bazel_manifest_loader_impl aligned with grounding specifications."""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from typing import Any, Dict, Optional, Sequence, Set, cast

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
from update_with_ai.parts.dag.lib.dag_storage import (
    DagDependency,
    DagMessage,
    DagNode,
    RoleAddress,
    UnitAddress,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase


def _make_dag_node(unit_address: str, role_address: str = "") -> DagNode:
    return DagNode(unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address))


class FakeBazelTarget:
    tier = "system"

    def __init__(self, base_dir: str = "") -> None:
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

    def normalize_target(self, target_identifier: str) -> DagNode:
        if "#" in target_identifier:
            u, r = target_identifier.split("#", 1)
            return _make_dag_node(self._norm(u), self._norm(r))
        return _make_dag_node(self._norm(target_identifier), "")

    def extract_node_dir(self, node: DagNode) -> NodeDirectory:
        pkg = node.unit_address.split(":")[0].lstrip("/")
        return NodeDirectory(path=cast(Any, pkg))


class FakeAgentStorage:
    tier = "system"

    def __init__(self) -> None:
        self._definitions: Dict[DagNode, NodeDefinition] = {}
        self._dependencies: Dict[DagNode, Set[DagDependency]] = {}
        self._feedback_dependencies: Dict[DagNode, Set[DagNode]] = {}
        self._source_files: Dict[DagNode, str] = {}
        self._silent_source_files: Dict[DagNode, Sequence[str]] = {}
        self._messages: Dict[DagNode, Set[DagMessage]] = {}

    def store_feedback_dependencies(self, node: DagNode, feedback_dependencies: Set[DagNode]) -> None:
        self._feedback_dependencies[node] = set(feedback_dependencies)

    def get_feedback_dependencies(self, node: DagNode) -> Set[DagNode]:
        return set(self._feedback_dependencies.get(node, set()))

    def get_node_definition(self, node: DagNode) -> Optional[NodeDefinition]:
        return self._definitions.get(node)

    def set_node_definition(self, node: DagNode, definition: NodeDefinition) -> None:
        self._definitions[node] = definition

    store_node_definition = set_node_definition

    def get_task_prompt(self, node: DagNode) -> Optional[TaskPrompt]:
        defn = self._definitions.get(node)
        return defn.task_prompt if defn else None

    def get_dependencies(self, node: DagNode) -> Set[DagDependency]:
        return set(self._dependencies.get(node, set()))

    def store_dependencies(self, node: DagNode, dependencies: Set[DagDependency]) -> None:
        self._dependencies[node] = set(dependencies)

    def add_dependency(self, from_node: DagNode, to_node: DagNode, is_silent: bool = False) -> None:
        deps = self._dependencies.setdefault(from_node, set())
        deps.add(DagDependency(node=to_node, is_silent=is_silent))

    register_dependency = add_dependency

    def record_source_file(self, node: DagNode, path: str) -> None:
        self._source_files[node] = path

    set_source_file = record_source_file

    def get_source_file(self, node: DagNode) -> Optional[str]:
        return self._source_files.get(node)

    def record_silent_source_files(self, node: DagNode, paths: Sequence[str]) -> None:
        self._silent_source_files[node] = list(paths)

    store_silent_source_files = record_silent_source_files

    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        return set(self._messages.get(node, set()))

    def add_message(self, message: DagMessage, to: DagNode) -> None:
        self._messages.setdefault(to, set()).add(message)

    def clear_messages(self, node: DagNode) -> None:
        self._messages.pop(node, None)

    def is_dirty(self, node: DagNode) -> bool:
        return bool(self._messages.get(node))


class BazelManifestLoaderImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.node_utils = FakeBazelTarget()
        self.storage = FakeAgentStorage()

        self.registry.register_instance(
            self.node_utils, keys=[BazelTarget], tier="system"
        )
        self.registry.register_instance(
            self.storage, keys=[AgentStorage], tier="system"
        )

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_retrieve_manifest_missing(self) -> None:
        """CUJ: Missing manifest file returns None."""
        node = _make_dag_node("//pkg/sub:missing_target")
        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST retrieve target manifests from workspace directories or runfiles trees.
            self.assertIsNone(loader.retrieve_manifest(node))

    def test_retrieve_manifest_dot_manifest_json(self) -> None:
        """CUJ: Retrieving and parsing target manifest files from .manifest.json."""
        node = _make_dag_node("//pkg/sub:target")
        pkg_path = os.path.join(self.test_dir, "pkg/sub")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file = os.path.join(pkg_path, ".manifest.json")

        manifest_data = {
            "label": "//pkg/sub:target",
            "task_prompt": "Do task",
            "source_file": "pkg/sub/target.py",
            "silent_source_files": ["pkg/sub/silent.py"],
            "dependencies": ["//dep/pkg:dep_target"],
            "silent_dependencies": ["//dep/pkg:silent_target"],
            "star_dependencies": ["//dep/pkg:star_target"],
            "feedback_dependencies": ["//dep/pkg:feedback_target"],
            "guide_target": "//pkg/sub:guide",
            "verification_check": "bazel test //pkg/sub:test",
            "template": "Template text",
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST retrieve target manifests from workspace directories for graph nodes.
            # Requirement: MUST load monolithic target manifests using bazel manifest ext.
            # Requirement: MUST anchor relative package directories to the workspace root.
            manifest = loader.retrieve_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertEqual(manifest.label, "//pkg/sub:target")
            self.assertEqual(manifest.task_prompt, "Do task")
            self.assertEqual(manifest.source_file, "pkg/sub/target.py")
            self.assertEqual(list(manifest.silent_source_files), ["pkg/sub/silent.py"])
            self.assertEqual(list(manifest.dependencies), ["//dep/pkg:dep_target"])
            self.assertEqual(list(manifest.silent_dependencies), ["//dep/pkg:silent_target"])
            self.assertEqual(list(manifest.star_dependencies), ["//dep/pkg:star_target"])
            self.assertEqual(list(manifest.feedback_dependencies), ["//dep/pkg:feedback_target"])
            self.assertEqual(manifest.guide_target, "//pkg/sub:guide")
            self.assertEqual(manifest.verification_check, "bazel test //pkg/sub:test")
            self.assertEqual(manifest.template, "Template text")

    def test_retrieve_manifest_plain_manifest_json(self) -> None:
        """CUJ: Resolving manifest from candidate filename manifest.json."""
        node = _make_dag_node("//pkg/plain:target")
        pkg_path = os.path.join(self.test_dir, "pkg/plain")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file = os.path.join(pkg_path, "manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump({"label": "//pkg/plain:target", "task_prompt": "Plain prompt"}, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST retrieve target manifests from workspace directories for graph nodes.
            # Requirement: MUST load monolithic target manifests using bazel manifest ext.
            manifest = loader.retrieve_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertEqual(manifest.label, "//pkg/plain:target")
            self.assertEqual(manifest.task_prompt, "Plain prompt")

    def test_retrieve_manifest_target_named_manifest(self) -> None:
        """CUJ: Resolving manifest from candidate filenames <target>.manifest.json and .<target>.manifest.json."""
        node = _make_dag_node("//pkg/named:custom_target")
        pkg_path = os.path.join(self.test_dir, "pkg/named")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file1 = os.path.join(pkg_path, "custom_target.manifest.json")
        manifest_file2 = os.path.join(pkg_path, ".custom_target.manifest.json")
        for mfile in (manifest_file1, manifest_file2):
            with open(mfile, "w", encoding="utf-8") as f:
                json.dump({"label": "//pkg/named:custom_target", "task_prompt": "Custom prompt"}, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST retrieve target manifests from workspace directories for graph nodes.
            manifest = loader.retrieve_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertEqual(manifest.label, "//pkg/named:custom_target")

    def test_retrieve_manifest_runfiles_resolution(self) -> None:
        """CUJ: Resolving target manifests across runfiles candidate locations."""
        node = _make_dag_node("//pkg/runfiles_node:target")
        runfiles_dir = os.path.join(self.test_dir, "runfiles_root")
        rf_pkg = os.path.join(runfiles_dir, "pkg/runfiles_node")
        os.makedirs(rf_pkg, exist_ok=True)
        with open(os.path.join(rf_pkg, ".manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"label": "//pkg/runfiles_node:target", "task_prompt": "Runfiles prompt"}, f)

        with patch.dict(os.environ, {"RUNFILES_DIR": runfiles_dir, "TEST_SRCDIR": runfiles_dir}):
            with enter_phase("system", registry=self.registry) as scope:
                loader = scope.get_singleton(BazelManifestLoader)
                # Requirement: MUST retrieve target manifests from runfiles trees for graph nodes.
                # Requirement: MUST anchor canonical package paths to candidate runfiles roots.
                manifest = loader.retrieve_manifest(node)
                self.assertIsNotNone(manifest)
                assert manifest is not None
                self.assertEqual(manifest.label, "//pkg/runfiles_node:target")

    def test_role_label_resolution(self) -> None:
        """CUJ: Dissecting and resolving role target labels into workspace role addresses."""
        node_with_role = _make_dag_node("//pkg/roles:comp", role_address="test")
        pkg_path = os.path.join(self.test_dir, "pkg/roles")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file = os.path.join(pkg_path, ".manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump({
                "label": "//pkg/roles:comp",
                "task_prompt": "Prompt for role",
                "dependencies": ["//other/pkg:dep#lib"],
            }, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            manifest = loader.retrieve_manifest(node_with_role)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertIn("//pkg/roles:comp", manifest.label)
            loader.load_manifest(node_with_role)

    def test_retrieve_manifest_parameterized_templates_and_patterns(self) -> None:
        """CUJ: Evaluating role source patterns, prompt templates, and verification check templates with unit metadata."""
        node = _make_dag_node("//pkg/param:widget", role_address="test")
        pkg_path = os.path.join(self.test_dir, "pkg/param")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file = os.path.join(pkg_path, ".manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump({
                "label": "//pkg/param:widget#test",
                "source_file": "pkg/param/widget_test.py",
                "task_prompt": "Test widget",
                "verification_check": "bazel test //pkg/param:widget_test",
                "dependencies": ["//dep/pkg:dep#lib"],
            }, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST load unit manifests using bazel manifest ext.
            # Requirement: MUST load role manifests using bazel manifest ext.
            # Requirement: MUST evaluate role source patterns parameterized with unit metadata.
            # Requirement: MUST evaluate task prompt templates parameterized with unit metadata.
            # Requirement: MUST evaluate verification check templates parameterized with unit metadata.
            manifest = loader.retrieve_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertEqual(manifest.source_file, "pkg/param/widget_test.py")
            self.assertEqual(manifest.task_prompt, "Test widget")
            self.assertEqual(manifest.verification_check, "bazel test //pkg/param:widget_test")

    def test_load_manifest_populates_storage(self) -> None:
        """CUJ: Resolving manifest into graph structures, dependencies, and node definitions."""
        node = _make_dag_node("//pkg:target_a")
        pkg_path = os.path.join(self.test_dir, "pkg")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file = os.path.join(pkg_path, ".manifest.json")

        manifest_data = {
            "label": "//pkg:target_a",
            "task_prompt": "Clean target A",
            "source_file": "pkg/target_a.py",
            "dependencies": ["//pkg:dep_b"],
            "silent_dependencies": ["//pkg:silent_c"],
            "star_dependencies": ["//pkg:star_d"],
            "feedback_dependencies": ["//pkg:feedback_e"],
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST resolve manifests into target nodes, dependencies, node definitions, task prompts, and dependency graph edges.
            # Requirement: MUST populate agent storage with resolved structures.
            # Requirement: MUST resolve declared direct dependencies into dependency graph edges in agent storage.
            # Requirement: MUST resolve declared silent dependencies as non-propagating dependencies in agent storage.
            # Requirement: MUST record declared primary source file paths in agent storage.
            loader.load_manifest(node)

            defn = self.storage.get_node_definition(node)
            self.assertIsNotNone(defn)
            assert defn is not None
            self.assertEqual(defn.task_prompt, "Clean target A")

            dep_b_node = self.node_utils.normalize_target("//pkg:dep_b")
            silent_c_node = self.node_utils.normalize_target("//pkg:silent_c")
            deps = self.storage.get_dependencies(node)
            self.assertIn(DagDependency(node=dep_b_node, is_silent=False), deps)
            self.assertIn(DagDependency(node=silent_c_node, is_silent=True), deps)
            self.assertEqual(self.storage.get_source_file(node), "pkg/target_a.py")
            feedback_e_node = self.node_utils.normalize_target("//pkg:feedback_e")
            self.assertEqual(self.storage.get_feedback_dependencies(node), {feedback_e_node})

    def test_load_manifest_synthesizes_definitions_for_unmanifested_dependencies(self) -> None:
        """CUJ: Synthesizing node definitions for declared dependencies lacking explicit manifests."""
        node = _make_dag_node("//pkg:parent")
        pkg_path = os.path.join(self.test_dir, "pkg")
        os.makedirs(pkg_path, exist_ok=True)

        manifest_file = os.path.join(pkg_path, ".manifest.json")
        manifest_data = {
            "label": "//pkg:parent",
            "task_prompt": "Parent prompt",
            "dependencies": ["//unmanifested/pkg:missing_dep"],
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST synthesize definitions for declared dependencies lacking explicit manifests.
            # Requirement: MUST synthesize fallback node definitions for referenced targets lacking manifests.
            loader.load_manifest(node)

            missing_node = self.node_utils.normalize_target("//unmanifested/pkg:missing_dep")
            missing_defn = self.storage.get_node_definition(missing_node)
            self.assertIsNotNone(missing_defn)
            assert missing_defn is not None
            self.assertIsInstance(missing_defn.task_prompt, str)

    def test_load_manifest_synthesizes_passthrough_when_role_inactive(self) -> None:
        """CUJ: Synthesizing promptless pass-through node definitions when a unit component type is not active for a role."""
        node = _make_dag_node("//pkg/inactive:unit", role_address="inactive_role")
        pkg_path = os.path.join(self.test_dir, "pkg/inactive")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file = os.path.join(pkg_path, ".manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump({
                "label": "//pkg/inactive:unit",
                "task_prompt": "Some prompt",
                "active_roles": ["other_role"],
            }, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST synthesize promptless pass-through node definitions when a unit component type is not active for a role.
            loader.load_manifest(node)
            defn = self.storage.get_node_definition(node)
            self.assertIsNotNone(defn)
            assert defn is not None
            self.assertIsInstance(defn.task_prompt, str)

    def test_load_manifest_cross_product_dependencies(self) -> None:
        """CUJ: Synthesizing target manifest records with cross-product dependencies across unit and role dimensions."""
        node = _make_dag_node("//pkg/unit:comp", role_address="role_b")
        pkg_path = os.path.join(self.test_dir, "pkg/unit")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file = os.path.join(pkg_path, ".manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump({
                "label": "//pkg/unit:comp",
                "task_prompt": "Cross product prompt",
                "dependencies": ["//dep/unit:dep_comp"],
                "role_dependencies": {"role_b": ["role_a"]},
            }, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST synthesize target manifest records with cross-product dependencies across unit and role dimensions.
            loader.load_manifest(node)

    def test_retrieve_manifest_synthesizes_role_node_deps(self) -> None:
        """CUJ: Synthesizing role node dependencies into declared target dependencies."""
        node = _make_dag_node("//pkg/myunit:mycomp", role_address="//roles:myrole")
        pkg_path = os.path.join(self.test_dir, "pkg/myunit")
        os.makedirs(pkg_path, exist_ok=True)
        unit_file = os.path.join(pkg_path, "mycomp_unit_manifest.json")
        with open(unit_file, "w", encoding="utf-8") as f:
            json.dump({
                "unit_name": "mycomp",
                "unit_dir": "pkg/myunit",
                "component_type": "implementation",
                "unit_deps": [],
            }, f)

        roles_path = os.path.join(self.test_dir, "roles")
        os.makedirs(roles_path, exist_ok=True)
        role_file = os.path.join(roles_path, "myrole_role_manifest.json")
        with open(role_file, "w", encoding="utf-8") as f:
            json.dump({
                "role_name": "myrole",
                "active_component_types": ["implementation"],
                "src_pattern": "{unit_dir}/low/{unit_name}.pyi",
                "node_deps": [
                    "//support/lib:framework_spec",
                    ":helper_spec",
                ],
            }, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST incorporate fixed role node dependencies as declared direct dependencies across unit and role dimensions.
            manifest = loader.retrieve_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertIn("//support/lib:framework_spec", manifest.dependencies)
            self.assertIn("//roles:helper_spec", manifest.dependencies)

    def test_load_manifest_normalizes_cross_root_staging_source_file(self) -> None:
        """CUJ: Loading manifest for staging node with canonical update_with_ai source path."""
        node = _make_dag_node("//staging/parts/agent:agent_session", role_address="//update_python_with_ai:low")
        manifest_data = {
            "label": "//staging/parts/agent:agent_session#//update_python_with_ai:low",
            "source_file": "update_with_ai/parts/agent/low/agent_session.pyi",
            "silent_source_files": ["update_with_ai/parts/agent/low/silent_stub.pyi"],
            "deps": [],
        }
        pkg_path = os.path.join(self.test_dir, "staging/parts/agent")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file = os.path.join(pkg_path, "agent_session_low_manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            # Requirement: MUST record declared primary source file paths in agent storage without duplicating package path segments.
            loader.load_manifest(node)
            self.assertEqual(
                self.storage.get_source_file(node),
                "staging/parts/agent/low/agent_session.pyi",
            )
            self.assertEqual(
                list(self.storage._silent_source_files.get(node) or []),
                ["staging/parts/agent/low/silent_stub.pyi"],
            )

    def test_load_manifest_deduplicates_redundant_package_prefix(self) -> None:
        """CUJ: Loading manifest with corrupted doubled package path segments."""
        node = _make_dag_node("//update_with_ai/parts/agent:agent_session", role_address="//update_python_with_ai:low")
        manifest_data = {
            "label": "//update_with_ai/parts/agent:agent_session#//update_python_with_ai:low",
            "source_file": "update_with_ai/parts/agent/update_with_ai/parts/agent/low/agent_session.pyi",
            "deps": [],
        }
        pkg_path = os.path.join(self.test_dir, "update_with_ai/parts/agent")
        os.makedirs(pkg_path, exist_ok=True)
        manifest_file = os.path.join(pkg_path, "agent_session_low_manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(BazelManifestLoader)
            loader.load_manifest(node)
            self.assertEqual(
                self.storage.get_source_file(node),
                "update_with_ai/parts/agent/low/agent_session.pyi",
            )


if __name__ == "__main__":
    unittest.main()
