import json
import os
import re
import subprocess
import tempfile
from typing import Optional, Sequence, Set
import unittest
from unittest.mock import MagicMock, patch
from lib.agent_storage import NodeDefinition
from lib.bazel_manifest_loader import BazelManifestLoader, Manifest
from lib.bazel_node_config_impl import (
    AliasManager as AliasManagerImpl,
    NodeConfig as NodeConfigImpl,
    _CommandVerificationCheck,
    _make_host_path,
    _parse_guide_markdown,
    __initialize__,
)
from lib.bazel_target import BazelTarget, NodeDirectory
from lib.dag_node_cleaner import CleanedNode
from lib.dag_storage import DagStorage, Feedback, Message, Node
from lib.agent_file_alias import (
    AliasManager,
    BoundFile,
    FileAlias,
    ReadOnlyFile,
    ReadWriteFile,
    UnboundFile,
    WorkspacePath,
)
from support.lib.lifecycle import LifecycleRegistry, Singleton, enter_phase
from lib.agent_config import AgentConfig
from lib.agent_node_config import Guide, NodeConfig, StepSection
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
            # Requirement: [NodeConfig] The node config provides the session guide file when step mode is active.
            self.assertEqual(cfg.guide_file, unbound)
            # Requirement: The node config exposes the declared guide target as the task guide when step mode is active.
            # Requirement: [NodeConfig] The node config provides the session guide, providing structured instructional text when step mode is active.
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
            # Requirement: The node config exposes whether step mode is active, enabled when the agent config enables step mode, the node allows step mode, and session feedback is absent.
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

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
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
        reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])
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

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = "agent_session"
            def normalize(self, raw_label: str) -> Node:
                return Node(address=raw_label)
            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("test/pkg")

        class MockDagStorage(DagStorage, Singleton):
            tier = "system"
            def get_messages(self, node: Node) -> Set[Message]:
                return set()

        class MockAgentConfig(AgentConfig, Singleton):
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
            def conversation_limit(self) -> int:
                return 20

        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register(MockCleanedNode, keys=[CleanedNode])
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])
        reg.register(MockDagStorage, keys=[DagStorage])
        reg.register(MockAgentConfig, keys=[AgentConfig])

        with enter_phase("system", registry=reg) as sys_scope:
            with enter_phase("agent_session", registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)
                alias_mgr = scope.get_singleton(AliasManager)

                # Requirement: The node config exposes whether the node allows step mode from the target node manifest.
                # Requirement: [NodeConfig] The node config indicates whether the node allows step mode.
                self.assertFalse(cfg.allows_step_mode)
                # Requirement: The node config exposes whether step mode is active, enabled when the agent config enables step mode, the node allows step mode, and session feedback is absent.
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
        """CUJ: When session feedback is present, step mode is disabled even if agent_config and node allow it, and guide is kept as read-only file."""
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

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = "agent_session"
            def normalize(self, raw_label: str) -> Node:
                return Node(address=raw_label)
            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("test/pkg")

        class MockDagStorage(DagStorage, Singleton):
            tier = "system"
            def get_messages(self, node: Node) -> Set[Message]:
                return {Feedback(content="Fix failing mock test")}

        class MockAgentConfig(AgentConfig, Singleton):
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
            def conversation_limit(self) -> int:
                return 20

        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register(MockCleanedNode, keys=[CleanedNode])
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])
        reg.register(MockDagStorage, keys=[DagStorage])
        reg.register(MockAgentConfig, keys=[AgentConfig])

        with enter_phase("system", registry=reg) as sys_scope:
            with enter_phase("agent_session", registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)
                alias_mgr = scope.get_singleton(AliasManager)

                # Requirement: The node config exposes whether the node allows step mode from the target node manifest.
                # Requirement: [NodeConfig] The node config indicates whether the node allows step mode.
                self.assertTrue(cfg.allows_step_mode)
                self.assertEqual(cfg.feedback, ("Fix failing mock test",))
                # Requirement: The node config exposes whether step mode is active, enabled when the agent config enables step mode, the node allows step mode, and session feedback is absent.
                # Requirement: [NodeConfig] The node config indicates whether session step mode is active.
                self.assertFalse(cfg.is_step_mode)
                self.assertIsNone(cfg.guide_file)
                self.assertIsNone(cfg.guide)

                # Declared guide dependencies are excluded from read-only files when step mode is active, and included as read-only files when step mode is inactive.
                ro_names = {f.short_name for f in cfg.read_only_files}
                self.assertIn("qa.md", ro_names)

                alias = alias_mgr.convert("qa.md")
                self.assertIsInstance(alias, ReadOnlyFile)

    @patch("lib.bazel_node_config_impl.subprocess.run")
    def test_command_verification_check_stderr_and_errors(self, mock_run: MagicMock) -> None:
        """CUJ: _CommandVerificationCheck handles stderr output, combined output, and subprocess errors."""
        check = _CommandVerificationCheck(command="test_cmd", cwd="/tmp")

        # Stderr only on failure
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="compilation error")
        passed, diag = check.verify()
        # Requirement: The node config exposes declared verification checks from the manifest verification command.
        # Requirement: [NodeConfig] The node config provides the session verification checks evaluated during session advancement.
        self.assertFalse(passed)
        self.assertEqual(diag, "compilation error")

        # Stdout and Stderr together
        mock_run.return_value = MagicMock(returncode=0, stdout="some warning", stderr="non-fatal warning")
        passed, diag = check.verify()
        self.assertTrue(passed)
        self.assertEqual(diag, "some warning\nnon-fatal warning")

        # SubprocessError exception
        mock_run.side_effect = subprocess.SubprocessError("subprocess crashed")
        passed, diag = check.verify()
        self.assertFalse(passed)
        self.assertIn("subprocess crashed", diag)

        # OSError exception
        mock_run.side_effect = OSError("command not found")
        passed, diag = check.verify()
        self.assertFalse(passed)
        self.assertIn("command not found", diag)

    def test_node_config_initialize_exception_guards(self) -> None:
        """CUJ: NodeConfig.initialize handles missing CleanedNode, missing/failing DagStorage, and missing/invalid manifest."""
        # 1. CleanedNode missing -> returns early without error
        reg1 = LifecycleRegistry()
        __initialize__(reg1)
        with enter_phase("agent_session", registry=reg1) as scope:
            cfg = scope.get_singleton(NodeConfig)
            self.assertEqual(cfg.read_write_files, set())

        # 2. DagStorage missing / failing -> self._feedback = ()
        class MockCleanedNode(CleanedNode, Singleton):
            tier = "agent_session"
            @property
            def node(self) -> Node:
                return Node(address="//pkg:tgt")

        class MockManifestLoaderNone(BazelManifestLoader, Singleton):
            tier = "agent_session"
            def get_manifest(self, node: Node) -> Optional[Manifest]:
                return None
            def load_manifest(self, content: Manifest, storage: object) -> Sequence[NodeDefinition]:
                return []

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = "agent_session"
            def normalize(self, raw_label: str) -> Node:
                return Node(address=raw_label)
            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("pkg")

        reg2 = LifecycleRegistry()
        __initialize__(reg2)
        reg2.register(MockCleanedNode, keys=[CleanedNode])
        reg2.register(MockManifestLoaderNone, keys=[BazelManifestLoader])
        reg2.register(MockNodeIdentifierUtility, keys=[BazelTarget])

        with enter_phase("agent_session", registry=reg2) as scope:
            cfg = scope.get_singleton(NodeConfig)
            # Requirement: Declared feedback messages retrieved from graph storage for the target node as the session feedback.
            # Requirement: [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.
            self.assertEqual(cfg.feedback, ())
            # Manifest is None -> returns early
            self.assertEqual(cfg.read_write_files, set())

        # 3. Manifest is invalid JSON -> returns early
        class MockManifestLoaderBadJson(BazelManifestLoader, Singleton):
            tier = "agent_session"
            def get_manifest(self, node: Node) -> Optional[Manifest]:
                return Manifest("invalid JSON {")
            def load_manifest(self, content: Manifest, storage: object) -> Sequence[NodeDefinition]:
                return []

        reg3 = LifecycleRegistry()
        __initialize__(reg3)
        reg3.register(MockCleanedNode, keys=[CleanedNode])
        reg3.register(MockManifestLoaderBadJson, keys=[BazelManifestLoader])
        reg3.register(MockNodeIdentifierUtility, keys=[BazelTarget])

        with enter_phase("agent_session", registry=reg3) as scope:
            cfg = scope.get_singleton(NodeConfig)
            self.assertEqual(cfg.read_write_files, set())

    def test_template_resolution_and_parameters_and_verification_message(self) -> None:
        """CUJ: Loading template content across candidate paths, handling JSON string parameters, and verification success message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "template.py")
            with open(template_path, "w", encoding="utf-8") as f:
                f.write("# Template code\n")

            class MockCleanedNode(CleanedNode, Singleton):
                tier = "agent_session"
                @property
                def node(self) -> Node:
                    return Node(address="//pkg:my_target")

            class MockManifestLoader(BazelManifestLoader, Singleton):
                tier = "agent_session"
                def get_manifest(self, node: Node) -> Optional[Manifest]:
                    return Manifest(json.dumps({
                        "src": "impl.py",
                        "template": template_path,
                        "template_parameters": json.dumps({"key": "value"}),
                        "verification_success_message": "Build passed successfully",
                    }))
                def load_manifest(self, content: Manifest, storage: object) -> Sequence[NodeDefinition]:
                    return []

            class MockNodeIdentifierUtility(BazelTarget, Singleton):
                tier = "agent_session"
                def normalize(self, raw_label: str) -> Node:
                    return Node(address=raw_label)
                def extract_directory(self, node: Node) -> NodeDirectory:
                    return _make_node_directory("pkg")

            reg = LifecycleRegistry()
            __initialize__(reg)
            reg.register(MockCleanedNode, keys=[CleanedNode])
            reg.register(MockManifestLoader, keys=[BazelManifestLoader])
            reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])

            with enter_phase("agent_session", registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)

                # Requirement: The node config exposes templates mapping read-write files to initial file content.
                # Requirement: [NodeConfig] The node config provides templates mapping read-write files to initial file content.
                self.assertEqual(len(cfg.templates), 1)
                for bound_f, content in cfg.templates:
                    self.assertEqual(bound_f.short_name, "impl.py")
                    self.assertEqual(content, "# Template code\n")

                # Requirement: The node config exposes declared template parameters from the manifest.
                # Requirement: [NodeConfig] The node config provides the session template parameters, providing parameter bindings for template evaluation.
                self.assertEqual(cfg.template_parameters, {"key": "value"})

                # Requirement: Declared verification success message from the manifest as the session verification success message.
                # Requirement: [NodeConfig] The node config provides the session verification success message when configured.
                self.assertEqual(cfg.verification_success_message, "Build passed successfully")

    def test_template_and_guide_read_errors_and_invalid_param_string(self) -> None:
        """CUJ: Gracefully handling read errors in template/guide resolution and invalid JSON parameter string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "template.py")
            with open(template_path, "w", encoding="utf-8") as f:
                f.write("content")

            guide_dir = os.path.join(tmpdir, "update_python_with_ai", "guides")
            os.makedirs(guide_dir, exist_ok=True)
            guide_path = os.path.join(guide_dir, "my_guide.md")
            with open(guide_path, "w", encoding="utf-8") as f:
                f.write("guide text")

            class MockCleanedNode(CleanedNode, Singleton):
                tier = "agent_session"
                @property
                def node(self) -> Node:
                    return Node(address="//pkg:my_target")

            class MockManifestLoader(BazelManifestLoader, Singleton):
                tier = "agent_session"
                def get_manifest(self, node: Node) -> Optional[Manifest]:
                    return Manifest(json.dumps({
                        "src": "impl.py",
                        "template": template_path,
                        "template_parameters": "not valid json {",
                        "guide": "//update_python_with_ai/guides:my_guide",
                        "allows_step_mode": True,
                    }))
                def load_manifest(self, content: Manifest, storage: object) -> Sequence[NodeDefinition]:
                    return []

            class MockNodeIdentifierUtility(BazelTarget, Singleton):
                tier = "agent_session"
                def normalize(self, raw_label: str) -> Node:
                    return Node(address=raw_label)
                def extract_directory(self, node: Node) -> NodeDirectory:
                    return _make_node_directory("pkg")

            class MockAgentConfig(AgentConfig, Singleton):
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
                def conversation_limit(self) -> int:
                    return 20

            reg = LifecycleRegistry()
            __initialize__(reg)
            reg.register(MockCleanedNode, keys=[CleanedNode])
            reg.register(MockManifestLoader, keys=[BazelManifestLoader])
            reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])
            reg.register(MockAgentConfig, keys=[AgentConfig])

            original_open = open
            def failing_open(path, *args, **kwargs):
                if path in (template_path, guide_path):
                    raise OSError("Simulated read failure")
                return original_open(path, *args, **kwargs)

            old_env_runfiles = os.environ.get("RUNFILES_DIR")
            old_env_bazel_runfiles = os.environ.get("BAZEL_RUNFILES")
            old_env_ws = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            try:
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = tmpdir
                os.environ["RUNFILES_DIR"] = tmpdir
                os.environ["BAZEL_RUNFILES"] = tmpdir

                with patch("builtins.open", side_effect=failing_open):
                    with enter_phase("system", registry=reg) as sys_scope:
                        with enter_phase("agent_session", registry=reg) as scope:
                            cfg = scope.get_singleton(NodeConfig)
                            # Template read failure results in empty templates
                            # Requirement: The node config exposes templates mapping read-write files to initial file content.
                            # Requirement: [NodeConfig] The node config provides templates mapping read-write files to initial file content.
                            self.assertEqual(cfg.templates, set())
                            # Invalid JSON param string results in default empty dict
                            # Requirement: The node config exposes declared template parameters from the manifest.
                            # Requirement: [NodeConfig] The node config provides the session template parameters, providing parameter bindings for template evaluation.
                            self.assertEqual(cfg.template_parameters, {})
                            # Guide read failure results in guide being None
                            # Requirement: The node config exposes the declared guide target as the guide file when step mode is active.
                            # Requirement: [NodeConfig] The node config provides the session guide file when step mode is active.
                            self.assertIsNotNone(cfg.guide_file)
                            self.assertIsNone(cfg.guide)
            finally:
                if old_env_runfiles is not None:
                    os.environ["RUNFILES_DIR"] = old_env_runfiles
                else:
                    os.environ.pop("RUNFILES_DIR", None)
                if old_env_bazel_runfiles is not None:
                    os.environ["BAZEL_RUNFILES"] = old_env_bazel_runfiles
                else:
                    os.environ.pop("BAZEL_RUNFILES", None)
                if old_env_ws is not None:
                    os.environ["BUILD_WORKSPACE_DIRECTORY"] = old_env_ws
                else:
                    os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)

    def test_step_mode_active_guide_parsing_and_alias_manager(self) -> None:
        """CUJ: Step mode actively parses markdown guide, skips lint checks, captures verification failure, and registers guide file alias."""
        # Test guide with Verification failure in middle and Lint checks at the end
        g_mid_vf = (
            "Summary text\n\n"
            "## Step 1\nContent 1\n\n"
            "## Verification failure\nVF instructions\n\n"
            "## Lint checks\nLint instructions\n"
        )
        parsed1 = _parse_guide_markdown(g_mid_vf)
        self.assertEqual(parsed1.summary, "Summary text")
        self.assertEqual(parsed1.verification_failure, "VF instructions")
        self.assertEqual(len(parsed1.sections), 1)

        # Test guide with Lint checks in middle, normal step at end
        g_mid_lint = (
            "Summary\n\n"
            "## Lint checks\nLint instructions\n\n"
            "## Final Step\nFinal instructions\n"
        )
        parsed2 = _parse_guide_markdown(g_mid_lint)
        self.assertEqual(len(parsed2.sections), 1)
        self.assertEqual(parsed2.sections[0].title, "Final Step")

        guide_content = (
            "This is the summary of the task.\n\n"
            "## Step 1: Write code\n"
            "Implement the feature according to spec.\n\n"
            "## Lint checks\n"
            "Run flake8 and mypy.\n\n"
            "## Step 2: Test code\n"
            "Verify with bazel test.\n\n"
            "## Verification failure\n"
            "Review error diagnostics and retry.\n"
        )
        parsed_guide = _parse_guide_markdown(guide_content)
        self.assertEqual(parsed_guide.summary, "This is the summary of the task.")
        self.assertEqual(len(parsed_guide.sections), 2)
        self.assertEqual(parsed_guide.sections[0].title, "Step 1: Write code")
        self.assertEqual(parsed_guide.sections[1].title, "Step 2: Test code")
        self.assertEqual(parsed_guide.verification_failure, "Review error diagnostics and retry.")

        with tempfile.TemporaryDirectory() as tmpdir:
            guides_dir = os.path.join(tmpdir, "update_python_with_ai", "guides")
            os.makedirs(guides_dir, exist_ok=True)
            guide_file_path = os.path.join(guides_dir, "my_guide.md")
            with open(guide_file_path, "w", encoding="utf-8") as f:
                f.write(guide_content)

            class MockCleanedNode(CleanedNode, Singleton):
                tier = "agent_session"
                @property
                def node(self) -> Node:
                    return Node(address="//pkg:my_target")

            class MockManifestLoader(BazelManifestLoader, Singleton):
                tier = "agent_session"
                def get_manifest(self, node: Node) -> Optional[Manifest]:
                    return Manifest(json.dumps({
                        "src": "impl.py",
                        "guide": "//update_python_with_ai/guides:my_guide",
                        "allows_step_mode": True,
                        "deps": ["//update_python_with_ai/guides:my_guide"],
                    }))
                def load_manifest(self, content: Manifest, storage: object) -> Sequence[NodeDefinition]:
                    return []

            class MockNodeIdentifierUtility(BazelTarget, Singleton):
                tier = "agent_session"
                def normalize(self, raw_label: str) -> Node:
                    return Node(address=raw_label)
                def extract_directory(self, node: Node) -> NodeDirectory:
                    return _make_node_directory("pkg")

            class MockAgentConfig(AgentConfig, Singleton):
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
                def conversation_limit(self) -> int:
                    return 20

            reg = LifecycleRegistry()
            __initialize__(reg)
            reg.register(MockCleanedNode, keys=[CleanedNode])
            reg.register(MockManifestLoader, keys=[BazelManifestLoader])
            reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])
            reg.register(MockAgentConfig, keys=[AgentConfig])

            old_env = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            try:
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = tmpdir
                with enter_phase("system", registry=reg) as sys_scope:
                    with enter_phase("agent_session", registry=reg) as scope:
                        cfg = scope.get_singleton(NodeConfig)
                        alias_mgr = scope.get_singleton(AliasManager)

                        # Requirement: The node config exposes whether step mode is active, enabled when the agent config enables step mode, the node allows step mode, and session feedback is absent.
                        # Requirement: [NodeConfig] The node config indicates whether session step mode is active.
                        self.assertTrue(cfg.is_step_mode)

                        # Requirement: The node config exposes the declared guide target as the guide file when step mode is active.
                        # Requirement: [NodeConfig] The node config provides the session guide file when step mode is active.
                        self.assertIsNotNone(cfg.guide_file)
                        assert cfg.guide_file is not None
                        self.assertEqual(cfg.guide_file.short_name, "my_guide.md")

                        # Requirement: The node config exposes the declared guide target as the task guide when step mode is active.
                        # Requirement: [NodeConfig] The node config provides the session guide, providing structured instructional text when step mode is active.
                        self.assertIsNotNone(cfg.guide)
                        assert cfg.guide is not None
                        self.assertEqual(cfg.guide.summary, "This is the summary of the task.")
                        self.assertEqual(len(cfg.guide.sections), 2)
                        self.assertEqual(cfg.guide.verification_failure, "Review error diagnostics and retry.")

                        # Guide is excluded from read_only_files when step mode is active
                        # Requirement: The node config exposes declared direct dependencies and transitive star dependencies resolved across dependency manifests using the bazel manifest loader as the session's read-only files, excluding silent dependencies.
                        # Requirement: [NodeConfig] The node config provides the session read-only files restricted to inspection.
                        ro_names = {f.short_name for f in cfg.read_only_files}
                        self.assertNotIn("my_guide.md", ro_names)

                        # Guide file is registered in AliasManager
                        # Requirement: The alias manager converts short names to matching file aliases, producing unbound files when unmapped.
                        # Requirement: [AliasManager] Converting a wire type string produces the matching file alias if its short name is found, and produces an unbound file if the short name is not found.
                        converted_guide = alias_mgr.convert("my_guide.md")
                        self.assertEqual(converted_guide, cfg.guide_file)
            finally:
                if old_env is not None:
                    os.environ["BUILD_WORKSPACE_DIRECTORY"] = old_env
                else:
                    os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)

    def test_dependency_resolution_branches(self) -> None:
        """CUJ: Resolving star_deps with diamond graphs, invalid JSON, silent_deps, and manifest-less specs/other dependencies."""
        class MockCleanedNode(CleanedNode, Singleton):
            tier = "agent_session"
            @property
            def node(self) -> Node:
                return Node(address="//pkg:root")

        class MockManifestLoader(BazelManifestLoader, Singleton):
            tier = "agent_session"
            def get_manifest(self, node: Node) -> Optional[Manifest]:
                if node.address == "//pkg:root":
                    return Manifest(json.dumps({
                        "src": "root.py",
                        "deps": [
                            "//pkg:silent_dep",
                            "//pkg:bad_json_dep",
                            "//specs/grounding:foo_low",
                            "//specs/grounding:bar_grounding",
                            "//specs/high:baz_high",
                            "//other/pkg:util",
                        ],
                        "star_deps": ["//pkg:star_a", "//pkg:star_b"],
                        "silent_deps": ["//pkg:silent_dep"],
                    }))
                if node.address == "//pkg:star_a":
                    return Manifest(json.dumps({
                        "src": "star_a.py",
                        "star_deps": ["//pkg:star_diamond", "//pkg:star_bad_json"],
                    }))
                if node.address == "//pkg:star_b":
                    return Manifest(json.dumps({
                        "src": "star_b.py",
                        "star_deps": ["//pkg:star_diamond"],
                    }))
                if node.address == "//pkg:star_diamond":
                    return Manifest(json.dumps({
                        "src": "star_diamond.py",
                    }))
                if node.address == "//pkg:star_bad_json":
                    return Manifest("not valid json {")
                if node.address == "//pkg:bad_json_dep":
                    return Manifest("not valid json {")
                return None

            def load_manifest(self, content: Manifest, storage: object) -> Sequence[NodeDefinition]:
                return []

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = "agent_session"
            def normalize(self, raw_label: str) -> Node:
                return Node(address=raw_label)
            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("pkg")

        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register(MockCleanedNode, keys=[CleanedNode])
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])

        with enter_phase("agent_session", registry=reg) as scope:
            cfg = scope.get_singleton(NodeConfig)

            # Requirement: The node config exposes declared direct dependencies and transitive star dependencies resolved across dependency manifests using the bazel manifest loader as the session's read-only files, excluding silent dependencies.
            # Requirement: [NodeConfig] The node config provides the session read-only files restricted to inspection.
            ro_names = {f.short_name for f in cfg.read_only_files}
            self.assertNotIn("silent_dep.py", ro_names)
            self.assertIn("star_a.py", ro_names)
            self.assertIn("star_b.py", ro_names)
            self.assertIn("star_diamond.py", ro_names)
            self.assertIn("foo.pyi", ro_names)
            self.assertIn("bar_grounding.pyi", ro_names)
            self.assertIn("baz.md", ro_names)
            self.assertIn("util.py", ro_names)

    def test_make_host_path_and_alias_manager_guards_and_fallback(self) -> None:
        """CUJ: _make_host_path with str subclass, AliasManager.initialize failure guard, and sanitize_text direct path fallback."""
        # 1. _make_host_path with str subclass
        class CustomPath(str):
            pass
        path_obj = _make_host_path(CustomPath, "foo/bar")
        self.assertIsInstance(path_obj, CustomPath)
        self.assertEqual(path_obj, "foo/bar")

        # 2. AliasManager.initialize failure guard (NodeConfig missing)
        reg = LifecycleRegistry()
        reg.register_singleton(
            AliasManagerImpl,
            keys=[AliasManager],
            tier="agent_session",
        )
        with enter_phase("agent_session", registry=reg) as scope:
            alias_mgr = scope.get_singleton(AliasManager)
            assert isinstance(alias_mgr, AliasManagerImpl)
            self.assertEqual(len(alias_mgr._aliases), 0)

        # 3. sanitize_text direct path fallback
        assert isinstance(alias_mgr, AliasManagerImpl)
        alias_mgr._paths["/non_regex_matched/custom_path.py"] = "custom_path.py"
        text = "Path without word boundary: [/non_regex_matched/custom_path.py]"
        sanitized = alias_mgr.sanitize_text(text)
        # Requirement: The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its minimal short name, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking.
        # Requirement: [AliasManager] Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with the corresponding file alias short names.
        self.assertEqual(sanitized, "Path without word boundary: [custom_path.py]")


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None


