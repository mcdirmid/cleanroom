# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:02Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 3a3d60b418d5
# COVERAGE_AUDIT: 2026-10-09T21:19:02Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for uv_manifest_loader_impl aligned with low-level specifications."""

import os
import shutil
import tempfile
import unittest
from typing import Dict, Optional, Sequence, Set

from update_with_ai.parts.agent.lib.agent_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.uv.lib.uv_manifest_loader import (
    UvManifestLoader,
    TargetManifest,
)
from update_with_ai.parts.uv.lib.uv_manifest_loader_impl import (
    UvManifestLoader as UvManifestLoaderImpl,
    __initialize__,
)
from update_with_ai.parts.core.lib import file_paths
from update_with_ai.parts.uv.lib.uv_target import UvTarget, NodeDirectory, TargetIdentifier
from update_with_ai.parts.dag.lib.dag_storage import (
    DagDependency,
    DagMessage,
    DagNode,
    RoleAddress,
    UnitAddress,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase


def _make_dag_node(unit_address: str, role_address: str = "") -> DagNode:
    return DagNode(
        unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address)
    )


class FakeUvTarget:
    tier = "system"

    def normalize_target(
        self, target_identifier: TargetIdentifier
    ) -> DagNode:
        ident_str = str(target_identifier).strip()
        role_part = ""
        if "#" in ident_str:
            ident_str, role_part = ident_str.split("#", 1)
        if ":" not in ident_str:
            pkg = ident_str
            target_name = pkg.split("/")[-1] if "/" in pkg else pkg
            ident_str = f"{pkg}:{target_name}"
        return DagNode(unit_address=UnitAddress(ident_str), role_address=RoleAddress(role_part))

    def extract_node_dir(self, node: DagNode) -> NodeDirectory:
        raw_pkg = node.unit_address.split(":", 1)[0].lstrip("/")
        return NodeDirectory(file_paths.PathString(raw_pkg))


class FakeAgentStorage:
    tier = "system"

    def __init__(self) -> None:
        self._definitions: Dict[DagNode, NodeDefinition] = {}
        self._dependencies: Dict[DagNode, Set[DagDependency]] = {}
        self._feedback_dependencies: Dict[DagNode, Set[DagNode]] = {}
        self._source_files: Dict[DagNode, str] = {}
        self._silent_source_files: Dict[DagNode, Sequence[str]] = {}
        self._messages: Dict[DagNode, Set[DagMessage]] = {}

    def store_feedback_dependencies(
        self, node: DagNode, feedback_dependencies: Set[DagNode]
    ) -> None:
        self._feedback_dependencies[node] = set(feedback_dependencies)

    def get_feedback_dependencies(self, node: DagNode) -> Set[DagNode]:
        return set(self._feedback_dependencies.get(node, set()))

    def get_node_definition(self, node: DagNode) -> Optional[NodeDefinition]:
        return self._definitions.get(node)

    def store_node_definition(self, node: DagNode, definition: NodeDefinition) -> None:
        self._definitions[node] = definition

    def get_dependencies(self, node: DagNode) -> Set[DagDependency]:
        return set(self._dependencies.get(node, set()))

    def store_dependencies(
        self, node: DagNode, dependencies: Set[DagDependency]
    ) -> None:
        self._dependencies[node] = set(dependencies)

    def record_source_file(self, node: DagNode, path: str) -> None:
        self._source_files[node] = path

    def get_source_file(self, node: DagNode) -> Optional[str]:
        return self._source_files.get(node)

    def store_silent_source_files(self, node: DagNode, paths: Sequence[str]) -> None:
        self._silent_source_files[node] = list(paths)

    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        return set(self._messages.get(node, set()))

    def add_message(self, message: DagMessage, to: DagNode) -> None:
        self._messages.setdefault(to, set()).add(message)

    def clear_messages(self, node: DagNode) -> None:
        self._messages.pop(node, None)

    def is_dirty(self, node: DagNode) -> bool:
        return bool(self._messages.get(node))


class TestUvManifestLoaderImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.test_dir

        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        self.target_utils = FakeUvTarget()
        self.storage = FakeAgentStorage()

        self.registry.register_instance(
            self.target_utils, keys=[UvTarget], tier="system"
        )
        self.registry.register_instance(
            self.storage, keys=[AgentStorage], tier="system"
        )

        # Setup mock cleanroom_python_roles.toml
        toml_content = """
[roles.lib]
src_pattern = "{unit_dir}/lib/{unit_name}.py"
prompt_template = "Implement {unit_name} as {component_type} in {unit_dir}/lib/{unit_name}.py"
verify_template = "pytest {unit_dir}/tests/{unit_name}_test.py"
guide = "//guides:lib"
active_component_types = ["implementation"]
role_deps = ["low"]
star_role_deps = ["lib"]
feedback_role_deps = ["qa"]
silent_role_deps = ["low"]
allows_step_mode = true

[roles.spec_qa]
src_pattern = ""
prompt_template = "Audit spec for {unit_name}"
verify_template = ""
guide = "//guides:spec_qa"
active_component_types = ["implementation", "assembly"]
role_deps = ["high", "planning"]
star_role_deps = []
feedback_role_deps = ["planning"]
silent_role_deps = []
allows_step_mode = false
"""
        with open(os.path.join(self.test_dir, "cleanroom_python_roles.toml"), "w", encoding="utf-8") as f:
            f.write(toml_content)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_retrieve_manifest_happy_path(self) -> None:
        """CUJ: Retrieving and evaluating target manifest for active role."""
        node = _make_dag_node("//pkg/sub:my_unit", "lib")
        high_dir = os.path.join(self.test_dir, "pkg/sub/high")
        os.makedirs(high_dir, exist_ok=True)
        hls_file = os.path.join(high_dir, "my_unit.md")
        with open(hls_file, "w", encoding="utf-8") as f:
            f.write("# implementation component\n\nimports: //other/pkg:other_unit\nimplements: iface_unit\n\n## Summary\n")

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(UvManifestLoader)
            manifest = loader.retrieve_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None

            self.assertEqual(manifest.label, "//pkg/sub:my_unit#lib")
            self.assertEqual(manifest.source_file, "pkg/sub/lib/my_unit.py")
            self.assertEqual(
                manifest.task_prompt,
                "Implement my_unit as implementation in pkg/sub/lib/my_unit.py",
            )
            self.assertEqual(
                manifest.verification_check, "pytest pkg/sub/tests/my_unit_test.py"
            )
            self.assertEqual(manifest.guide_target, "//guides:lib")
            self.assertTrue(manifest.allows_step_mode)

            # Dependencies: intra-unit role_dep (//pkg/sub:my_unit#low)
            # plus inter-unit star_role_deps from imports (//other/pkg:other_unit#lib)
            # and implements (//pkg/sub:iface_unit#lib)
            expected_deps = {
                "//pkg/sub:my_unit#low",
                "//other/pkg:other_unit#lib",
                "//pkg/sub:iface_unit#lib",
            }
            self.assertEqual(set(manifest.dependencies), expected_deps)
            self.assertEqual(set(manifest.silent_dependencies), {"//pkg/sub:my_unit#low"})
            self.assertEqual(set(manifest.feedback_dependencies), {"//pkg/sub:my_unit#qa"})

    def test_retrieve_manifest_inactive_component_type(self) -> None:
        """CUJ: Synthesizing promptless pass-through node when component type is not active."""
        node = _make_dag_node("//pkg/sub:asm_unit", "lib")
        high_dir = os.path.join(self.test_dir, "pkg/sub/high")
        os.makedirs(high_dir, exist_ok=True)
        hls_file = os.path.join(high_dir, "asm_unit.md")
        with open(hls_file, "w", encoding="utf-8") as f:
            f.write("# assembly component\n\nassembles: part1, part2\n")

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(UvManifestLoader)
            manifest = loader.retrieve_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None

            self.assertEqual(manifest.label, "//pkg/sub:asm_unit#lib")
            self.assertIsNone(manifest.task_prompt)
            self.assertIsNone(manifest.source_file)
            self.assertFalse(manifest.allows_step_mode)
            expected = {
                "//pkg/sub:part1#lib",
                "//pkg/sub:part2#lib",
                "//pkg/sub:asm_unit#low",
            }
            self.assertEqual(set(manifest.dependencies), expected)

    def test_retrieve_manifest_cross_package_bare_unit(self) -> None:
        """CUJ: Resolving bare unit name across sibling packages in parts root."""
        os.makedirs(os.path.join(self.test_dir, "parts/pkg_a/high"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "parts/pkg_b/high"), exist_ok=True)
        with open(os.path.join(self.test_dir, "parts/pkg_a/high/unit_a.md"), "w", encoding="utf-8") as f:
            f.write("# implementation component\n\n## Summary\n")
        with open(os.path.join(self.test_dir, "parts/pkg_b/high/unit_b.md"), "w", encoding="utf-8") as f:
            f.write("# implementation component\n\nimports: unit_a\n\n## Summary\n")

        node = _make_dag_node("//parts/pkg_b:unit_b", "lib")
        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(UvManifestLoader)
            manifest = loader.retrieve_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            # Must resolve bare unit_a to //parts/pkg_a:unit_a#lib, not //parts/pkg_b:unit_a#lib
            self.assertIn("//parts/pkg_a:unit_a#lib", manifest.dependencies)

    def test_load_manifest_populates_storage(self) -> None:
        """CUJ: Loading manifest populates agent and dag storage."""
        node = _make_dag_node("//pkg/sub:my_unit", "lib")
        high_dir = os.path.join(self.test_dir, "pkg/sub/high")
        os.makedirs(high_dir, exist_ok=True)
        hls_file = os.path.join(high_dir, "my_unit.md")
        with open(hls_file, "w", encoding="utf-8") as f:
            f.write("# implementation component\n\nimports: //dep/pkg:dep\n")

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(UvManifestLoader)
            loader.load_manifest(node)

            node_def = self.storage.get_node_definition(node)
            self.assertIsNotNone(node_def)
            assert node_def is not None
            self.assertEqual(
                node_def.task_prompt,
                "Implement my_unit as implementation in pkg/sub/lib/my_unit.py",
            )
            self.assertEqual(
                self.storage.get_source_file(node), "pkg/sub/lib/my_unit.py"
            )

            deps = self.storage.get_dependencies(node)
            dep_nodes = {d.node: d.is_silent for d in deps}
            low_dep = _make_dag_node("//pkg/sub:my_unit", "low")
            other_dep = _make_dag_node("//dep/pkg:dep", "lib")
            self.assertIn(low_dep, dep_nodes)
            self.assertTrue(dep_nodes[low_dep])
            self.assertIn(other_dep, dep_nodes)
            self.assertFalse(dep_nodes[other_dep])

            fb_deps = self.storage.get_feedback_dependencies(node)
            qa_dep = _make_dag_node("//pkg/sub:my_unit", "qa")
            self.assertEqual(fb_deps, {qa_dep})

    def test_retrieve_manifest_assembly_with_assembles(self) -> None:
        """CUJ: Assembly component role evaluating assembles dependencies."""
        node = _make_dag_node("//pkg/sub:asm_unit", "spec_qa")
        high_dir = os.path.join(self.test_dir, "pkg/sub/high")
        os.makedirs(high_dir, exist_ok=True)
        hls_file = os.path.join(high_dir, "asm_unit.md")
        with open(hls_file, "w", encoding="utf-8") as f:
            f.write("# asm_unit assembly component\n\nassembles: part1, //other:part2\n")

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(UvManifestLoader)
            manifest = loader.retrieve_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertEqual(manifest.label, "//pkg/sub:asm_unit#spec_qa")
            self.assertEqual(manifest.task_prompt, "Audit spec for asm_unit")
            self.assertFalse(manifest.allows_step_mode)
            self.assertIn("//pkg/sub:asm_unit#high", manifest.dependencies)
            self.assertIn("//pkg/sub:asm_unit#planning", manifest.dependencies)

    def test_load_manifest_inactive_type(self) -> None:
        """CUJ: Loading manifest for inactive component type stores empty NodeDefinition."""
        node = _make_dag_node("//pkg/sub:asm_unit", "lib")
        high_dir = os.path.join(self.test_dir, "pkg/sub/high")
        os.makedirs(high_dir, exist_ok=True)
        hls_file = os.path.join(high_dir, "asm_unit.md")
        with open(hls_file, "w", encoding="utf-8") as f:
            f.write("# asm_unit assembly component\n\nassembles: part1\n")

        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(UvManifestLoader)
            loader.load_manifest(node)

            node_def = self.storage.get_node_definition(node)
            self.assertIsNotNone(node_def)
            assert node_def is not None
            self.assertEqual(node_def.task_prompt, "")

    def test_retrieve_manifest_missing_hls(self) -> None:
        """CUJ: When HLS is missing, returns None."""
        node = _make_dag_node("//pkg/sub:no_hls", "lib")
        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(UvManifestLoader)
            manifest = loader.retrieve_manifest(node)
            self.assertIsNone(manifest)

    def test_retrieve_manifest_upward_methodology_search(self) -> None:
        """CUJ: Upward search from package directory discovers cleanroom.toml methodology binding."""
        pkg_dir = os.path.join(self.test_dir, "pkg")
        os.makedirs(os.path.join(pkg_dir, "sub", "high"), exist_ok=True)
        with open(os.path.join(pkg_dir, "cleanroom.toml"), "w", encoding="utf-8") as f:
            f.write('methodology = "//custom_methodology"\n')

        custom_meth_dir = os.path.join(self.test_dir, "custom_methodology")
        os.makedirs(custom_meth_dir, exist_ok=True)
        custom_toml = """
[roles.lib]
src_pattern = "{unit_dir}/lib/{unit_name}.py"
prompt_template = "CUSTOM PROMPT for {unit_name}"
active_component_types = ["implementation"]
"""
        with open(os.path.join(custom_meth_dir, "cleanroom_roles.toml"), "w", encoding="utf-8") as f:
            f.write(custom_toml)

        with open(os.path.join(pkg_dir, "sub", "high", "custom_unit.md"), "w", encoding="utf-8") as f:
            f.write("# custom_unit implementation component\n")

        node = _make_dag_node("//pkg/sub:custom_unit", "lib")
        with enter_phase("system", registry=self.registry) as scope:
            loader = scope.get_singleton(UvManifestLoader)
            manifest = loader.retrieve_manifest(node)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertEqual(manifest.task_prompt, "CUSTOM PROMPT for custom_unit")


if __name__ == "__main__":
    unittest.main()
