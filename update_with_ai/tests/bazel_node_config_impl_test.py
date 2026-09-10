import json
import os
import re
from typing import Optional, Sequence
import unittest
from lib.bazel_graph_storage import NodeDefinition
from lib.bazel_manifest_loader import BazelManifestLoader, Manifest
from lib.bazel_node_config_impl import (
    AliasManager as AliasManagerImpl,
    NodeConfig as NodeConfigImpl,
    __initialize__,
)
from lib.bazel_node_id_utils import BazelNodeIdentifierUtility, NodeDirectory
from lib.dag_node_cleaner import CleanedNode
from lib.dag_storage import Node
from lib.file_alias import (
    AliasManager,
    BoundFile,
    FileAlias,
    ReadOnlyFile,
    ReadWriteFile,
    UnboundFile,
    WorkspacePath,
)
from support.lib.lifecycle import LifecycleRegistry, Singleton, enter_phase
from lib.node_config import NodeConfig
from lib.sandbox_guide_delivery import Guide, StepSection
from lib.tool_provider import ParameterConverter, String


def _make_workspace_path(path: str) -> WorkspacePath:
    obj = object.__new__(WorkspacePath)
    object.__setattr__(obj, "path", path)
    return obj


def _make_node_directory(path: str) -> NodeDirectory:
    obj = object.__new__(NodeDirectory)
    object.__setattr__(obj, "path", path)
    return obj


class BazelNodeConfigImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_node_config_properties(self) -> None:
        """CUJ: Accessing NodeConfig properties for declared files, templates, and guidance."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            cfg = scope.get_singleton(NodeConfig)
            self.assertIsInstance(cfg, NodeConfigImpl)
            assert isinstance(cfg, NodeConfigImpl)

            # Defaults
            self.assertEqual(cfg.read_only_files, set())
            self.assertEqual(cfg.read_write_files, set())
            self.assertEqual(cfg.templates, set())
            self.assertIsNone(cfg.guide_file)
            self.assertIsNone(cfg.guide)
            self.assertEqual(cfg.blame_targets, set())
            self.assertEqual(cfg.verification_checks, [])

            # Configure properties
            node = Node(address="//pkg:target")
            ro = ReadOnlyFile(
                short_name="ro.txt",
                workspace_path=_make_workspace_path("pkg/ro.txt"),
                owning_node=node,
            )
            rw = ReadWriteFile(
                short_name="rw.txt",
                workspace_path=_make_workspace_path("pkg/rw.txt"),
                owning_node=node,
            )
            unbound = UnboundFile(short_name="guide.md")
            guide = Guide(summary="Guide", sections=[StepSection(0, "S1", "C1")])

            cfg._read_only_files.add(ro)
            cfg._read_write_files.add(rw)
            cfg._templates.add((rw, "template"))
            cfg._guide_file = unbound
            cfg._guide = guide
            cfg._blame_targets.add(ro)

            # Requirement: The node config exposes declared direct dependencies and transitive star dependencies resolved across dependency manifests using the bazel manifest loader as the session's read-only files, excluding silent dependencies.
            # Requirement: [NodeConfig] The node config provides the session's read-only files restricted to inspection.
            self.assertIn(ro, cfg.read_only_files)
            # Requirement: The node config exposes declared source files and silent source files as read-write files.
            # Requirement: [NodeConfig] The node config provides the session's read-write files permitted for inspection and modification.
            self.assertIn(rw, cfg.read_write_files)
            # Requirement: The node config exposes templates mapping read-write files to initial file content.
            # Requirement: [NodeConfig] The node config provides templates mapping read-write files to initial file content.
            self.assertIn((rw, "template"), cfg.templates)
            # Requirement: The node config exposes the declared guide target as the guide file when step mode is active.
            # Requirement: [NodeConfig] The node config provides the session's guide file when progressive guidance is active, or absent if no guide file is configured.
            self.assertEqual(cfg.guide_file, unbound)
            # Requirement: The node config exposes the declared guide target as the task guide when step mode is active.
            # Requirement: [NodeConfig] The node config provides the session's guide for progressive guidance, or absent if no guide is configured.
            self.assertEqual(cfg.guide, guide)
            # Requirement: The node config exposes declared feedback dependencies as blame targets mapped to owning dependency nodes.
            # Requirement: [NodeConfig] The node config provides blame targets eligible for defect attribution.
            self.assertIn(ro, cfg.blame_targets)

            class DummyCheck:
                def verify(self):
                    return True, "ok"
            dummy_check = DummyCheck()
            cfg._verification_checks.append(dummy_check)
            # Requirement: The node config exposes declared verification checks from the manifest verification command.
            # Requirement: [NodeConfig] The node config provides the session's verification checks evaluated during session advancement.
            self.assertIn(dummy_check, cfg.verification_checks)

    def test_alias_manager_converter_and_sanitization(self) -> None:
        """CUJ: AliasManager converts short names to FileAlias and sanitizes host paths."""
        with enter_phase("agent_session", registry=self.registry) as scope:
            alias_mgr = scope.get_singleton(AliasManager)
            self.assertIsInstance(alias_mgr, AliasManagerImpl)
            assert isinstance(alias_mgr, AliasManagerImpl)

            # Parameter converter interface
            self.assertEqual(alias_mgr.actual_type, FileAlias)
            self.assertEqual(alias_mgr.wire_type, String())
            self.assertIs(scope.get_singleton(ParameterConverter), alias_mgr)
            self.assertIsNotNone(alias_mgr.workspace_root)

            # Map an alias
            node = Node(address="//pkg:target")
            bound = ReadWriteFile(
                short_name="module.py",
                workspace_path=_make_workspace_path("pkg/module.py"),
                owning_node=node,
            )
            alias_mgr._aliases["module.py"] = bound
            alias_mgr._paths["/workspace/pkg/module.py"] = "module.py"

            # Convert mapped short name
            converted = alias_mgr.convert("module.py")
            # Requirement: The alias manager converts short names to matching file aliases, producing unbound files when unmapped.
            # Requirement: [AliasManager] Converting a wire type string produces the matching file alias if its short name is found, and produces an unbound file if the short name is not found.
            self.assertEqual(converted, bound)

            # Convert unmapped short name produces UnboundFile
            unmapped = alias_mgr.convert("unknown.py")
            # Requirement: The alias manager converts short names to matching file aliases, producing unbound files when unmapped.
            # Requirement: [AliasManager] Converting a wire type string produces the matching file alias if its short name is found, and produces an unbound file if the short name is not found.
            self.assertIsInstance(unmapped, UnboundFile)
            self.assertEqual(unmapped.short_name, "unknown.py")

            # Sanitize text
            norm_ws = "pkg/module.py"
            pat = re.compile(
                r"/?(?:[^\s:;\"\'`()<>{}\[\]/]+/)*" + re.escape(norm_ws) + r"(?=[:\s;\"\'`()<>{}\[\]]|$)"
            )
            alias_mgr._masking_patterns.append((pat, "module.py"))

            text = "Error in /workspace/pkg/module.py at line 10"
            sanitized = alias_mgr.sanitize_text(text)
            # Requirement: The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its minimal short name, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking.
            # Requirement: [AliasManager] Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with the corresponding file alias short names.
            self.assertNotIn("/workspace/pkg/module.py", sanitized)
            self.assertIn("module.py", sanitized)

            prefix_text = "  /private/var/tmp/sandbox/pkg/module.py:5:38 - error: issue"
            prefix_sanitized = alias_mgr.sanitize_text(prefix_text)
            self.assertEqual(prefix_sanitized, "  module.py:5:38 - error: issue")

            rel_text = "Verification failed: pkg/module.py:2: error: msg"
            rel_sanitized = alias_mgr.sanitize_text(rel_text)
            self.assertEqual(rel_sanitized, "Verification failed: module.py:2: error: msg")

    def test_lifecycle_initialization_from_manifest(self) -> None:
        """CUJ: NodeConfig and AliasManager initialize from CleanedNode and BazelManifestLoader."""
        class MockCleanedNode(CleanedNode, Singleton):
            tier = "agent_session"
            def __init__(self) -> None:
                self._node = Node(address="//test/pkg:my_target")
            @property
            def node(self) -> Node:
                return self._node
            def set_node(self, node: Node) -> None:
                self._node = node

        class MockManifestLoader(BazelManifestLoader, Singleton):
            tier = "agent_session"
            def get_manifest(self, node: Node) -> Optional[Manifest]:
                if node.address == "//test/pkg:my_target":
                    return Manifest(json.dumps({
                        "src": "impl.py",
                        "silent_srcs": ["internal.py"],
                        "deps": ["//test/pkg:dep_target"],
                        "star_deps": ["//test/pkg:star_parent"],
                        "silent_deps": [],
                        "feedback_deps": ["//test/pkg:dep_target"],
                        "verify": "echo verified",
                    }))
                if node.address == "//test/pkg:dep_target":
                    return Manifest(json.dumps({
                        "src": "dep_target.py",
                    }))
                if node.address == "//test/pkg:star_parent":
                    return Manifest(json.dumps({
                        "src": "star_parent.py",
                        "star_deps": ["//test/pkg:star_transitive"],
                    }))
                if node.address == "//test/pkg:star_transitive":
                    return Manifest(json.dumps({
                        "src": "star_transitive.py",
                    }))
                return None
            def load_manifest(self, content: Manifest, storage: object) -> Sequence[NodeDefinition]:
                return []

        class MockNodeIdentifierUtility(BazelNodeIdentifierUtility, Singleton):
            tier = "agent_session"
            def normalize(self, raw_label: str) -> Node:
                return Node(address=raw_label)
            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("test/pkg")

        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register(MockCleanedNode, keys=[CleanedNode])
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelNodeIdentifierUtility])

        with enter_phase("agent_session", registry=reg) as scope:
            cfg = scope.get_singleton(NodeConfig)
            alias_mgr = scope.get_singleton(AliasManager)

            # Requirement: The node config exposes declared source files and silent source files as read-write files.
            # Requirement: [NodeConfig] The node config provides the session's read-write files permitted for inspection and modification.
            rw_names = {f.short_name for f in cfg.read_write_files}
            self.assertIn("impl.py", rw_names)
            self.assertIn("internal.py", rw_names)

            # Requirement: The node config exposes declared direct dependencies and transitive star dependencies resolved across dependency manifests using the bazel manifest loader as the session's read-only files, excluding silent dependencies.
            # Requirement: [NodeConfig] The node config provides the session's read-only files restricted to inspection.
            ro_names = {f.short_name for f in cfg.read_only_files}
            self.assertIn("dep_target.py", ro_names)
            self.assertIn("star_parent.py", ro_names)
            self.assertIn("star_transitive.py", ro_names)

            # Requirement: The node config exposes declared feedback dependencies as blame targets mapped to owning dependency nodes.
            # Requirement: [NodeConfig] The node config provides blame targets eligible for defect attribution.
            blame_names = {f.short_name for f in cfg.blame_targets}
            self.assertIn("dep_target.py", blame_names)

            # Requirement: The node config exposes declared verification checks from the manifest verification command.
            # Requirement: [NodeConfig] The node config provides the session's verification checks evaluated during session advancement.
            self.assertEqual(len(cfg.verification_checks), 1)
            passed, diag = cfg.verification_checks[0].verify()
            self.assertTrue(passed)
            self.assertEqual(diag.strip(), "verified")

            # Requirement: The alias manager converts short names to matching file aliases, producing unbound files when unmapped.
            # Requirement: [AliasManager] Converting a wire type string produces the matching file alias if its short name is found, and produces an unbound file if the short name is not found.
            alias_impl = alias_mgr.convert("impl.py")
            self.assertIsInstance(alias_impl, ReadWriteFile)
            self.assertEqual(alias_impl.short_name, "impl.py")

            alias_dep = alias_mgr.convert("dep_target.py")
            self.assertIsInstance(alias_dep, ReadOnlyFile)
            self.assertEqual(alias_dep.short_name, "dep_target.py")

            # Sanitize text via lifecycle initialization
            diag_output = (
                "Verification failed: /sandbox/execroot/_main/test/pkg/impl.py:5: error: syntax\n"
                "test/pkg/dep_target.py:12: error: missing import"
            )
            sanitized = alias_mgr.sanitize_text(diag_output)
            # Requirement: The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its minimal short name, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking.
            # Requirement: [AliasManager] Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with the corresponding file alias short names.
            self.assertEqual(
                sanitized,
                "Verification failed: impl.py:5: error: syntax\n"
                "dep_target.py:12: error: missing import",
            )


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None

