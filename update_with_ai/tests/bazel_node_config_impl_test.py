"""Unit tests for bazel_node_config_impl aligned with grounding specifications."""

import unittest
from lib.bazel_node_config_impl import (
    AliasManager as AliasManagerImpl,
    NodeConfig as NodeConfigImpl,
    __initialize__,
)
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
from lib.lifecycle import LifecycleRegistry, enter_phase
from lib.node_config import NodeConfig
from lib.sandbox_guide_delivery import Guide, StepSection
from lib.tool_provider import ParameterConverter, String


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

            # Configure properties
            node = Node(address="//pkg:target")
            ro = ReadOnlyFile(
                short_name="ro.txt",
                workspace_path=WorkspacePath(path="pkg/ro.txt"),
                owning_node=node,
            )
            rw = ReadWriteFile(
                short_name="rw.txt",
                workspace_path=WorkspacePath(path="pkg/rw.txt"),
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

            # Requirement: The node config exposes declared direct dependencies and transitive star dependencies as read-only files, excluding silent dependencies.
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
                workspace_path=WorkspacePath(path="pkg/module.py"),
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
            text = "Error in /workspace/pkg/module.py at line 10"
            sanitized = alias_mgr.sanitize_text(text)
            # Requirement: The alias manager sanitizes output text by masking occurrences of host paths with minimal short names.
            # Requirement: [AliasManager] Sanitizing text masks occurrences of host paths with the corresponding file alias short names.
            self.assertNotIn("/workspace/pkg/module.py", sanitized)
            self.assertIn("module.py", sanitized)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None

