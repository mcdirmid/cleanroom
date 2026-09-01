"""Tests for manifest_node_loader_impl derived from LLS."""

import unittest
from typing import Sequence, Optional, Dict, List
from lib.dag_storage import NodeId, DagMessage, PendingMessage, NodeData
from lib.sandbox import SandboxConfig
from lib.node_id_utils import NodeIdUtils, NodeDirectory
from lib.build_graph_storage import BuildGraphStorage, NodeDefinition
from lib.manifest_node_loader_impl import ManifestLoaderImpl


class StubNodeIdUtils(NodeIdUtils):
    def canonicalize_node_id(self, raw_id: str, current_context: str = "") -> NodeId:
        s = raw_id.strip()
        if s.startswith("//"):
            return s if ":" in s else f"{s}:{s[2:]}"
        if s.startswith(":"):
            return f"//pkg{s}"
        return f"//{s}:{s}"

    def extract_node_directory(self, node: NodeId, workspace_root: str = "") -> NodeDirectory:
        s = node.strip()
        if s.startswith("//"):
            pkg = s[2:].split(":")[0]
            return pkg
        return ""


class StubBuildGraphStorage(BuildGraphStorage):
    def __init__(self) -> None:
        self.deps: Dict[NodeId, List[NodeId]] = {}
        self.rdeps: Dict[NodeId, List[NodeId]] = {}
        self.sandbox_configs: Dict[NodeId, SandboxConfig] = {}
        self.task_prompts: Dict[NodeId, Optional[str]] = {}
        self.node_definitions: Dict[NodeId, Optional[NodeDefinition]] = {}
        self.node_data: Dict[NodeId, NodeData] = {}
        self.dirty_nodes: Dict[NodeId, bool] = {}

    def set_dependencies(self, node: NodeId, deps: Sequence[NodeId]) -> None:
        self.deps[node] = list(deps)

    def get_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return self.deps.get(node, [])

    def get_reverse_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return self.rdeps.get(node, [])

    def get_pending_messages(self, node: NodeId) -> Sequence[PendingMessage]:
        return []

    def queue_pending_messages(self, node: NodeId, messages: Sequence[DagMessage]) -> None:
        pass

    def clear_pending_messages(self, node: NodeId) -> None:
        pass

    def record_node_data(self, node: NodeId, data: NodeData) -> None:
        self.node_data[node] = data

    def get_node_data(self, node: NodeId) -> Optional[NodeData]:
        return self.node_data.get(node)

    def mark_dirty(self, node: NodeId) -> None:
        self.dirty_nodes[node] = True

    def is_dirty(self, node: NodeId) -> bool:
        return self.dirty_nodes.get(node, False)

    def set_sandbox_config(self, node: NodeId, config: SandboxConfig) -> None:
        self.sandbox_configs[node] = config

    def get_sandbox_config(self, node: NodeId) -> SandboxConfig:
        return self.sandbox_configs[node]

    def set_task_prompt(self, node: NodeId, prompt: Optional[str]) -> None:
        self.task_prompts[node] = prompt

    def get_task_prompt(self, node: NodeId) -> Optional[str]:
        return self.task_prompts.get(node)

    def set_node_definition(self, node: NodeId, definition: Optional[NodeDefinition]) -> None:
        self.node_definitions[node] = definition

    def get_node_definition(self, node: NodeId) -> Optional[NodeDefinition]:
        return self.node_definitions.get(node)


class ManifestLoaderImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.node_id_utils = StubNodeIdUtils()

    def test_load_manifest_populates_dependencies_and_canonicalizes_labels(self) -> None:
        """Tests CUJ for parsing manifest and registering canonical target nodes and dependencies in storage."""
        storage = StubBuildGraphStorage()
        loader = ManifestLoaderImpl(node_id_utils=self.node_id_utils)
        manifest_json = """{
            "label": ":target_a",
            "deps": ["//pkg_b:target_b"],
            "dependency_paths": [
                {"label": "//pkg_b:target_b", "path": "pkg_b/target_b.py"}
            ]
        }"""
        defs = loader.load_manifest(manifest_json, storage)
        self.assertEqual(len(defs), 1)
        self.assertEqual(storage.get_dependencies("//pkg:target_a"), ["//pkg_b:target_b"])
        # Target_b was declared as dependency; synthesized empty definition should exist
        self.assertIsNotNone(storage.get_node_definition("//pkg_b:target_b"))

    def test_load_manifest_resolves_src_and_silent_srcs_to_rw_files(self) -> None:
        """Tests that declared src and silent_srcs are resolved relative to package directory into read_write_files."""
        storage = StubBuildGraphStorage()
        loader = ManifestLoaderImpl(node_id_utils=self.node_id_utils)
        manifest_json = """{
            "label": "//update_with_ai/specs:dag_storage_lib",
            "src": "dag_storage.py",
            "silent_srcs": ["dag_storage_meta.json"],
            "template": "templates/dag_storage.py.tpl",
            "prompt": "Implement dag_storage"
        }"""
        defs = loader.load_manifest(manifest_json, storage)
        self.assertEqual(len(defs), 1)
        cfg = defs[0].sandbox_config
        self.assertIn("dag_storage.py", cfg.read_write_files)
        self.assertIn("dag_storage_meta.json", cfg.read_write_files)
        self.assertEqual(
            cfg.templates.get("dag_storage.py"),
            "templates/dag_storage.py.tpl",
        )
        self.assertEqual(cfg.file_mappings.get("dag_storage.py"), "update_with_ai/specs/dag_storage.py")
        self.assertEqual(defs[0].prompt, "Implement dag_storage")

    def test_load_manifest_resolves_deps_and_star_deps_to_ro_files(self) -> None:
        """Tests that direct deps and star_deps resolve their source files into read_only_files via dependency_paths."""
        storage = StubBuildGraphStorage()
        loader = ManifestLoaderImpl(node_id_utils=self.node_id_utils)
        manifest_json = """{
            "label": "//pkg:consumer",
            "src": "consumer.py",
            "deps": ["//pkg_a:lib_a"],
            "star_deps": ["//pkg_b:lib_b"],
            "silent_deps": ["//pkg_silent:lib_silent"],
            "dependency_paths": [
                {"label": "//pkg_a:lib_a", "path": "pkg_a/lib_a.py"},
                {"label": "//pkg_b:lib_b", "path": "pkg_b/lib_b.py"},
                {"label": "//pkg_silent:lib_silent", "path": "pkg_silent/lib_silent.py"}
            ]
        }"""
        defs = loader.load_manifest(manifest_json, storage)
        cfg = defs[0].sandbox_config

        # Direct dep and star dep sources are in read_only_files
        self.assertIn("lib_a.py", cfg.read_only_files)
        self.assertIn("lib_b.py", cfg.read_only_files)
        self.assertEqual(cfg.file_mappings.get("lib_a.py"), "pkg_a/lib_a.py")
        self.assertEqual(cfg.file_mappings.get("lib_b.py"), "pkg_b/lib_b.py")

        # Silent dep source must NOT be in read_only_files
        self.assertNotIn("lib_silent.py", cfg.read_only_files)
        self.assertNotIn("pkg_silent/lib_silent.py", cfg.read_only_files)

        # But silent dep is registered as a dependency in storage
        all_deps = storage.get_dependencies("//pkg:consumer")
        self.assertIn("//pkg_a:lib_a", all_deps)
        self.assertIn("//pkg_silent:lib_silent", all_deps)

    def test_load_manifest_derives_minimal_virtual_file_names(self) -> None:
        """Tests virtual file name derivation: bare names when unique, minimal parent suffixes on collision."""
        storage = StubBuildGraphStorage()
        loader = ManifestLoaderImpl(node_id_utils=self.node_id_utils)
        manifest_json = """{
            "label": "//pkg:target",
            "src": "helpers.py",
            "deps": ["//other:helpers", "//cfg:settings"],
            "dependency_paths": [
                {"label": "//other:helpers", "path": "tests/unit/helpers.py"},
                {"label": "//cfg:settings", "path": "config/settings.py"}
            ]
        }"""
        defs = loader.load_manifest(manifest_json, storage)
        mappings = defs[0].sandbox_config.file_mappings

        # config/settings.py has no collision -> settings.py
        self.assertEqual(mappings.get("settings.py"), "config/settings.py")

        # pkg/helpers.py vs tests/unit/helpers.py collides on helpers.py -> disambiguated
        self.assertEqual(mappings.get("pkg/helpers.py"), "pkg/helpers.py")
        self.assertEqual(mappings.get("unit/helpers.py"), "tests/unit/helpers.py")


if __name__ == "__main__":
    unittest.main()
