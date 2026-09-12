import json
import os
import re
from typing import Optional, Sequence, Set
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
from lib.dag_storage import DagStorage, Feedback, Message, Node
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
from lib.model_config import ModelConfig
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
            self.assertEqual(cfg.template_parameters, {})
            self.assertTrue(cfg.allows_step_mode)
            self.assertFalse(cfg.is_step_mode)
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
            # Requirement: [NodeConfig] The node config provides the session read-only files restricted to inspection.
            self.assertIn(ro, cfg.read_only_files)
            # Requirement: The node config exposes declared source files and silent source files as read-write files.
            # Requirement: [NodeConfig] The node config provides the session read-write files permitted for inspection and modification.
            self.assertIn(rw, cfg.read_write_files)
            # Requirement: The node config exposes templates mapping read-write files to initial file content.
            # Requirement: [NodeConfig] The node config provides templates mapping read-write files to initial file content.
            self.assertIn((rw, "template"), cfg.templates)
            # Requirement: The node config exposes the declared guide target as the guide file when step mode is active.
            # Requirement: [NodeConfig] The node config provides the session guide file when guide step mode is configured.
            self.assertEqual(cfg.guide_file, unbound)
            # Requirement: The node config exposes the declared guide target as the task guide when step mode is active.
            # Requirement: [NodeConfig] The node config provides the session guide, providing structured instructional text when guide step mode is configured.
            self.assertEqual(cfg.guide, guide)
            cfg._feedback = ("Feedback msg 1",)
            # Requirement: Declared feedback messages retrieved from graph storage for the target node as the session feedback.
            # Requirement: [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.
            self.assertEqual(cfg.feedback, ("Feedback msg 1",))
            # Requirement: The node config exposes declared feedback dependencies as blame targets mapped to owning dependency nodes.
            # Requirement: [NodeConfig] The node config provides blame targets eligible for defect attribution.
            self.assertIn(ro, cfg.blame_targets)

            class DummyCheck:
                def verify(self):
                    return True, "ok"
            dummy_check = DummyCheck()
            cfg._verification_checks.append(dummy_check)
            # Requirement: The node config exposes declared verification checks from the manifest verification command.
            # Requirement: [NodeConfig] The node config provides the session verification checks evaluated during session advancement.
            self.assertIn(dummy_check, cfg.verification_checks)

            cfg._allows_step_mode = False
            cfg._is_step_mode = False
            # Requirement: The node config exposes whether the node allows step mode from the target node manifest.
            # Requirement: [NodeConfig] The node config indicates whether the node allows step mode.
            self.assertFalse(cfg.allows_step_mode)
            # Requirement: The node config exposes whether step mode is active, enabled when the model config enables step mode and the node allows step mode.
            # Requirement: [NodeConfig] The node config indicates whether session step mode is active.
            self.assertFalse(cfg.is_step_mode)
            cfg._allows_step_mode = True
            cfg._is_step_mode = True
            self.assertTrue(cfg.allows_step_mode)
            self.assertTrue(cfg.is_step_mode)

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
                        "template_parameters": {"module_name": "MyModule", "has_ops": True},
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

        class MockDagStorage(DagStorage, Singleton):
            tier = "system"
            def get_messages(self, node: Node) -> Set[Message]:
                msgs: Set[Message] = {Feedback(content="Fix type error")}
                return msgs

        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register(MockCleanedNode, keys=[CleanedNode])
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelNodeIdentifierUtility])
        reg.register(MockDagStorage, keys=[DagStorage])

        with enter_phase("system", registry=reg) as sys_scope:
            with enter_phase("agent_session", registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)
                alias_mgr = scope.get_singleton(AliasManager)

                # Requirement: Declared feedback messages retrieved from graph storage for the target node as the session feedback.
                # Requirement: [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.
                self.assertEqual(cfg.feedback, ("Fix type error",))
                self.assertEqual(cfg.template_parameters, {"module_name": "MyModule", "has_ops": True})

            # Requirement: The node config exposes declared source files and silent source files as read-write files.
            # Requirement: [NodeConfig] The node config provides the session read-write files permitted for inspection and modification.
            rw_names = {f.short_name for f in cfg.read_write_files}
            self.assertIn("impl.py", rw_names)
            self.assertIn("internal.py", rw_names)

            # Requirement: The node config exposes declared direct dependencies and transitive star dependencies resolved across dependency manifests using the bazel manifest loader as the session's read-only files, excluding silent dependencies.
            # Requirement: [NodeConfig] The node config provides the session read-only files restricted to inspection.
            ro_names = {f.short_name for f in cfg.read_only_files}
            self.assertIn("dep_target.py", ro_names)
            self.assertIn("star_parent.py", ro_names)
            self.assertIn("star_transitive.py", ro_names)

            # Requirement: The node config exposes declared feedback dependencies as blame targets mapped to owning dependency nodes.
            # Requirement: [NodeConfig] The node config provides blame targets eligible for defect attribution.
            blame_names = {f.short_name for f in cfg.blame_targets}
            self.assertIn("dep_target.py", blame_names)

            # Requirement: The node config exposes declared verification checks from the manifest verification command.
            # Requirement: [NodeConfig] The node config provides the session verification checks evaluated during session advancement.
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

    def test_lifecycle_initialization_step_mode_disabled(self) -> None:
        """CUJ: When allows_step_mode is false, step mode is disabled and guide is kept as read-only file."""
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
                        "guide": "//update_python_with_ai/guides:qa",
                        "allows_step_mode": False,
                        "deps": ["//update_python_with_ai/guides:qa"],
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

        class MockDagStorage(DagStorage, Singleton):
            tier = "system"
            def get_messages(self, node: Node) -> Set[Message]:
                return set()

        class MockModelConfig(ModelConfig, Singleton):
            tier = "system"
            @property
            def is_step_mode(self) -> bool:
                return True
            @property
            def is_startup_reads(self) -> bool:
                return True
            @property
            def inject_followups(self) -> bool:
                return True
            @property
            def model_name(self) -> str:
                return "test-model"
            @property
            def base_url(self) -> Optional[str]:
                return None
            @property
            def api_key(self) -> Optional[str]:
                return None
            @property
            def timeout(self) -> int:
                return 60
            @property
            def conversation_limit(self) -> int:
                return 20
            @property
            def temperature(self) -> float:
                return 0.0
            @property
            def max_tokens(self) -> Optional[int]:
                return None
            @property
            def node_visit_limit(self) -> int:
                return 500

        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register(MockCleanedNode, keys=[CleanedNode])
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelNodeIdentifierUtility])
        reg.register(MockDagStorage, keys=[DagStorage])
        reg.register(MockModelConfig, keys=[ModelConfig])

        with enter_phase("system", registry=reg) as sys_scope:
            with enter_phase("agent_session", registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)
                alias_mgr = scope.get_singleton(AliasManager)

                # Requirement: The node config exposes whether the node allows step mode from the target node manifest.
                # Requirement: [NodeConfig] The node config indicates whether the node allows step mode.
                self.assertFalse(cfg.allows_step_mode)
                # Requirement: The node config exposes whether step mode is active, enabled when the model config enables step mode and the node allows step mode.
                # Requirement: [NodeConfig] The node config indicates whether session step mode is active.
                self.assertFalse(cfg.is_step_mode)
                self.assertIsNone(cfg.guide_file)
                self.assertIsNone(cfg.guide)

                # Guide target is included in read_only_files
                ro_names = {f.short_name for f in cfg.read_only_files}
                self.assertIn("qa.md", ro_names)

                alias = alias_mgr.convert("qa.md")
                self.assertIsInstance(alias, ReadOnlyFile)

    def test_lifecycle_initialization_step_mode_disabled_when_feedback_present(self) -> None:
        """CUJ: When session feedback is present, step mode is disabled even if model_config and node allow it, and guide is kept as read-only file."""
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
                        "guide": "//update_python_with_ai/guides:qa",
                        "allows_step_mode": True,
                        "deps": ["//update_python_with_ai/guides:qa"],
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

        class MockDagStorage(DagStorage, Singleton):
            tier = "system"
            def get_messages(self, node: Node) -> Set[Message]:
                return {Feedback(content="Fix failing mock test")}

        class MockModelConfig(ModelConfig, Singleton):
            tier = "system"
            @property
            def is_step_mode(self) -> bool:
                return True
            @property
            def is_startup_reads(self) -> bool:
                return True
            @property
            def inject_followups(self) -> bool:
                return True
            @property
            def model_name(self) -> str:
                return "test-model"
            @property
            def base_url(self) -> Optional[str]:
                return None
            @property
            def api_key(self) -> Optional[str]:
                return None
            @property
            def timeout(self) -> int:
                return 60
            @property
            def conversation_limit(self) -> int:
                return 20
            @property
            def temperature(self) -> float:
                return 0.0
            @property
            def max_tokens(self) -> Optional[int]:
                return None
            @property
            def node_visit_limit(self) -> int:
                return 500

        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register(MockCleanedNode, keys=[CleanedNode])
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelNodeIdentifierUtility])
        reg.register(MockDagStorage, keys=[DagStorage])
        reg.register(MockModelConfig, keys=[ModelConfig])

        with enter_phase("system", registry=reg) as sys_scope:
            with enter_phase("agent_session", registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)
                alias_mgr = scope.get_singleton(AliasManager)

                # Requirement: The node config exposes whether the node allows step mode from the target node manifest.
                # Requirement: [NodeConfig] The node config indicates whether the node allows step mode.
                self.assertTrue(cfg.allows_step_mode)
                self.assertEqual(cfg.feedback, ("Fix failing mock test",))
                # Requirement: Step mode is active when model config step mode is enabled, the target node allows step mode, and session feedback is absent.
                # Requirement: The node config exposes whether step mode is active, enabled when the model config enables step mode and the node allows step mode and session feedback is absent.
                # Requirement: [NodeConfig] The node config indicates whether session step mode is active.
                self.assertFalse(cfg.is_step_mode)
                self.assertIsNone(cfg.guide_file)
                self.assertIsNone(cfg.guide)

                # Declared guide dependencies are excluded from read-only files when step mode is active, and included as read-only files when step mode is inactive.
                ro_names = {f.short_name for f in cfg.read_only_files}
                self.assertIn("qa.md", ro_names)

                alias = alias_mgr.convert("qa.md")
                self.assertIsInstance(alias, ReadOnlyFile)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None

