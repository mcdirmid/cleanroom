import json
import os
import re
import subprocess
import tempfile
from typing import Optional, Sequence, Set
import unittest
from unittest.mock import MagicMock, patch
from update_with_ai.parts.agent.lib.agent_storage import NodeDefinition
from update_with_ai.parts.bazel.lib.bazel_manifest_loader import (
    BazelManifestLoader,
    Manifest,
)
from update_with_ai.parts.bazel.lib.bazel_node_config_impl import (
    AliasManager as AliasManagerImpl,
    NodeConfig as NodeConfigImpl,
    _CommandVerificationCheck,
    _make_host_path,
    _parse_guide_markdown,
    __initialize__,
)
from update_with_ai.parts.agent.lib.agent_node_config import PerNodeInfo, RoleConfig
from update_with_ai.parts.bazel.lib.bazel_target import BazelTarget, NodeDirectory
from update_with_ai.parts.dag.lib.dag_storage import DagStorage, Feedback, Message, Node
from update_with_ai.parts.agent.lib.agent_file_alias import (
    AliasManager,
    BoundFile,
    FileAlias,
    ReadOnlyFile,
    ReadWriteFile,
    UnboundFile,
    WorkspacePath,
)
from support.lib.lifecycle import LifecycleRegistry, Singleton, enter_phase, system
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.agent.lib.agent_node_config import (
    Guide,
    NodeConfig,
    StepSection,
)
from update_with_ai.parts.sandbox.lib.tool_provider import (
    ParameterType,
    String,
)


def _make_workspace_path(path: str) -> WorkspacePath:
    obj = object.__new__(WorkspacePath)
    object.__setattr__(obj, "path", path)
    return obj


def _make_node_directory(path: str) -> NodeDirectory:
    obj = object.__new__(NodeDirectory)
    object.__setattr__(obj, "path", path)
    return obj


class MockRoleConfig(RoleConfig, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._role: str = "coder"
        self._nodes: Sequence[Node] = (Node(unit_address="//test/pkg:my_target"),)
        self._version: int = 1

    @property
    def role(self) -> str:
        return self._role

    @property
    def nodes(self) -> Sequence[Node]:
        return self._nodes

    @property
    def version(self) -> int:
        return self._version

    def set_node(self, node: Node) -> None:
        self._nodes = (node,)
        self._version += 1

    def set_nodes(self, nodes: Sequence[Node]) -> None:
        self._nodes = tuple(nodes)
        self._version += 1


class BazelNodeConfigImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.registry.register(MockRoleConfig, keys=[RoleConfig], phase=agent_session)

    def test_node_config_properties(self) -> None:
        """CUJ: Accessing NodeConfig properties for declared files, templates, and guidance."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            cfg: NodeConfigImpl = scope.get_singleton(NodeConfigImpl)
            self.assertIsInstance(cfg, NodeConfigImpl)

            role_cfg = scope.get_singleton(RoleConfig)
            assert isinstance(role_cfg, MockRoleConfig)
            role_cfg.set_nodes([])

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
            self.assertEqual(cfg.blame_targets_by_node, {})
            self.assertEqual(cfg.verification_checks, [])
            self.assertEqual(cfg.verification_checks_by_node, {})
            self.assertEqual(cfg.src_file_alias_by_node, {})
            self.assertEqual(cfg.per_node_info_by_node, {})

            # Configure properties
            node = Node(unit_address="//pkg:target")
            ro = ReadOnlyFile(
                relative_path="ro.txt",
                workspace_path=_make_workspace_path("pkg/ro.txt"),
                owning_node=node,
            )
            rw = ReadWriteFile(
                relative_path="rw.txt",
                workspace_path=_make_workspace_path("pkg/rw.txt"),
                owning_node=node,
            )
            unbound = UnboundFile(relative_path="guide.md")
            guide = Guide(summary="Guide", sections=[StepSection(0, "S1", "C1")])

            class DummyCheck:
                def verify(self):
                    return True, "ok"

            dummy_check = DummyCheck()

            role_cfg.set_nodes([node])

            info = PerNodeInfo(
                node=node,
                read_only_files={ro},
                read_write_files={rw},
                templates={(rw, "template")},
                template_parameters={"key": "value"},
                allows_step_mode=True,
                guide_file=unbound,
                guide=guide,
                blame_targets={ro},
                verification_checks=[dummy_check],
                src_file_alias="rw.txt",
                verification_success_message="All tests passed",
                feedback=("Feedback msg 1",),
            )

            cfg._per_node_cache[node] = info
            cfg._cached_version = role_cfg.version

            # Requirement: The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.
            # Requirement: [NodeConfig] The node config provides the session read-only files restricted to inspection.
            self.assertIn(ro, cfg.read_only_files)
            # Requirement: The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.
            # Requirement: [NodeConfig] The node config provides the session read-write files permitted for inspection and modification.
            self.assertIn(rw, cfg.read_write_files)
            # Requirement: The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.
            # Requirement: [NodeConfig] The node config provides templates mapping read-write files to initial file content.
            self.assertIn((rw, "template"), cfg.templates)
            # Requirement: The session template parameters combining template parameters across the active nodes.
            # Requirement: [NodeConfig] The node config provides the session template parameters, providing parameter bindings for template evaluation.
            self.assertEqual(cfg.template_parameters, {"key": "value"})

            cfg._is_step_mode_override = True
            # Requirement: The session guide file and task guide from the single active node when guide step mode is active.
            # Requirement: [NodeConfig] The node config provides the session guide file when step mode is active.
            self.assertEqual(cfg.guide_file, unbound)
            # Requirement: The session guide file and task guide from the single active node when guide step mode is active.
            # Requirement: [NodeConfig] The node config provides the session guide, providing structured instructional text when step mode is active.
            self.assertEqual(cfg.guide, guide)

            # Requirement: The session feedback combining feedback messages retrieved from graph storage across the active nodes.
            # Requirement: [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.
            self.assertEqual(cfg.feedback, ("Feedback msg 1",))
            # Requirement: The session blame targets aggregating blame targets across the active nodes, and blame targets by node mapping each active node to its declared blame targets.
            # Requirement: [NodeConfig] The node config provides blame targets eligible for defect attribution.
            self.assertIn(ro, cfg.blame_targets)
            # Requirement: The session blame targets aggregating blame targets across the active nodes, and blame targets by node mapping each active node to its declared blame targets.
            # Requirement: [NodeConfig] The node config provides the session blame targets mapped by session node.
            self.assertEqual(cfg.blame_targets_by_node[node], {ro})
            # Requirement: The session src file alias by node mapping each active node to the relative path of its declared source file alias.
            # Requirement: [NodeConfig] The node config provides the source file alias relative path mapped by session node.
            self.assertEqual(cfg.src_file_alias_by_node[node], "rw.txt")
            # Requirement: The session verification success message from the active node when the session contains exactly one node.
            # Requirement: [NodeConfig] The node config provides the session verification success message when configured.
            self.assertEqual(cfg.verification_success_message, "All tests passed")

            # Requirement: The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.
            # Requirement: [NodeConfig] The node config provides the session verification checks evaluated during session advancement.
            self.assertIn(dummy_check, cfg.verification_checks)
            # Requirement: The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.
            # Requirement: [NodeConfig] The node config provides the session verification checks mapped by session node.
            self.assertEqual(cfg.verification_checks_by_node[node], (dummy_check,))

            # Requirement: The session per node info by node mapping each active node to its per node info.
            # Requirement: [NodeConfig] The node config provides the session per node info by node, mapping each active node to its per node info.
            self.assertEqual(cfg.per_node_info_by_node[node], info)

            cfg._allows_step_mode_override = False
            cfg._is_step_mode_override = False
            # Requirement: Whether the node allows step mode resolved when the session contains exactly one node.
            # Requirement: [NodeConfig] The node config indicates whether the node allows step mode.
            self.assertFalse(cfg.allows_step_mode)
            # Requirement: Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.
            # Requirement: [NodeConfig] The node config indicates whether session step mode is active.
            self.assertFalse(cfg.is_step_mode)
            cfg._allows_step_mode_override = True
            cfg._is_step_mode_override = True
            self.assertTrue(cfg.allows_step_mode)
            self.assertTrue(cfg.is_step_mode)

    def test_alias_manager_converter_and_sanitization(self) -> None:
        """CUJ: AliasManager converts short names to FileAlias and sanitizes host paths."""
        with enter_phase(agent_session, registry=self.registry) as scope:
            alias_mgr = scope.get_singleton(AliasManager)
            self.assertIsInstance(alias_mgr, AliasManagerImpl)
            assert isinstance(alias_mgr, AliasManagerImpl)

            # Parameter converter interface
            self.assertEqual(alias_mgr.actual_type, FileAlias)
            self.assertEqual(alias_mgr.wire_type, str)
            self.assertIs(scope.get_singleton(ParameterType), alias_mgr)
            self.assertIsNotNone(alias_mgr.workspace_root)

            # Map an alias
            node = Node(unit_address="//pkg:target")
            bound = ReadWriteFile(
                relative_path="module.py",
                workspace_path=_make_workspace_path("pkg/module.py"),
                owning_node=node,
            )
            alias_mgr._aliases["module.py"] = bound
            alias_mgr._paths["/workspace/pkg/module.py"] = "module.py"

            # Convert mapped relative path
            converted = alias_mgr.convert("module.py")
            # Requirement: Converting a wire type string produces the matching file alias if its relative path is found, or if its short name unambiguously resolves to a single declared bound file, and produces an unbound file if the relative path is not found or is ambiguous.
            self.assertEqual(converted, bound)
            self.assertEqual(alias_mgr.to_actual("module.py"), bound)
            self.assertEqual(alias_mgr.to_wire(bound), "module.py")

            # Courtesy short-name resolution
            bound_nested = ReadWriteFile(
                relative_path="pkg/sub/nested.py",
                workspace_path=_make_workspace_path("pkg/sub/nested.py"),
                owning_node=node,
            )
            alias_mgr._aliases["pkg/sub/nested.py"] = bound_nested
            alias_mgr._short_name_to_aliases["nested.py"] = [bound_nested]

            # Unambiguous short name resolves to bound file
            # Requirement: Converting a wire type string produces the matching file alias if its relative path is found, or if its short name unambiguously resolves to a single declared bound file, and produces an unbound file if the relative path is not found or is ambiguous.
            resolved = alias_mgr.convert("nested.py")
            self.assertEqual(resolved, bound_nested)

            # Ambiguous short name falls back to UnboundFile
            bound_dup = ReadWriteFile(
                relative_path="other/sub/nested.py",
                workspace_path=_make_workspace_path("other/sub/nested.py"),
                owning_node=node,
            )
            alias_mgr._short_name_to_aliases["nested.py"].append(bound_dup)
            ambiguous = alias_mgr.convert("nested.py")
            # Requirement: Converting a wire type string produces the matching file alias if its relative path is found, or if its short name unambiguously resolves to a single declared bound file, and produces an unbound file if the relative path is not found or is ambiguous.
            self.assertIsInstance(ambiguous, UnboundFile)
            self.assertEqual(ambiguous.relative_path, "nested.py")

            # Convert unmapped relative path produces UnboundFile
            unmapped = alias_mgr.convert("unknown.py")
            # Requirement: Converting a wire type string produces the matching file alias if its relative path is found, or if its short name unambiguously resolves to a single declared bound file, and produces an unbound file if the relative path is not found or is ambiguous.
            self.assertIsInstance(unmapped, UnboundFile)
            self.assertEqual(unmapped.relative_path, "unknown.py")

            # Sanitize text
            norm_ws = "pkg/module.py"
            pat = re.compile(
                r"/?(?:[^\s:;\"\'`()<>{}\[\]/]+/)*"
                + re.escape(norm_ws)
                + r"(?=[:\s;\"\'`()<>{}\[\]]|$)"
            )
            alias_mgr._masking_patterns.append((pat, "module.py"))

            text = "Error in /workspace/pkg/module.py at line 10"
            sanitized = alias_mgr.sanitize_text(text)
            # Requirement: Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with the corresponding file alias relative paths.
            self.assertNotIn("/workspace/pkg/module.py", sanitized)
            self.assertIn("module.py", sanitized)

            prefix_text = "  /private/var/tmp/sandbox/pkg/module.py:5:38 - error: issue"
            prefix_sanitized = alias_mgr.sanitize_text(prefix_text)
            self.assertEqual(prefix_sanitized, "  module.py:5:38 - error: issue")

            rel_text = "Verification failed: pkg/module.py:2: error: msg"
            rel_sanitized = alias_mgr.sanitize_text(rel_text)
            self.assertEqual(
                rel_sanitized, "Verification failed: module.py:2: error: msg"
            )

            execroot_text = "FAIL: //target (Exit 1) (see /private/var/tmp/_bazel_user/1234abcd/execroot/_main/bazel-out/darwin_arm64-fastbuild/testlogs/target/test.log)"
            execroot_sanitized = alias_mgr.sanitize_text(execroot_text)
            self.assertEqual(
                execroot_sanitized,
                "FAIL: //target (Exit 1) (see bazel-out/darwin_arm64-fastbuild/testlogs/target/test.log)",
            )

    def test_lifecycle_initialization_from_manifest(self) -> None:
        """CUJ: NodeConfig and AliasManager initialize from RoleConfig and BazelManifestLoader."""

        class MockManifestLoader(BazelManifestLoader, Singleton):
            tier = agent_session

            def get_manifest(self, node: Node) -> Optional[Manifest]:
                if node.unit_address == "//test/pkg:my_target":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "impl.py",
                                "silent_srcs": ["internal.py"],
                                "deps": ["//test/pkg:dep_target"],
                                "star_deps": ["//test/pkg:star_parent"],
                                "silent_deps": [],
                                "feedback_deps": ["//test/pkg:dep_target"],
                                "template_parameters": {
                                    "module_name": "MyModule",
                                    "has_ops": True,
                                },
                                "verify": "echo verified",
                            }
                        )
                    )
                if node.unit_address == "//test/pkg:dep_target":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "dep_target.py",
                            }
                        )
                    )
                if node.unit_address == "//test/pkg:star_parent":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "star_parent.py",
                                "star_deps": ["//test/pkg:star_transitive"],
                            }
                        )
                    )
                if node.unit_address == "//test/pkg:star_transitive":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "star_transitive.py",
                            }
                        )
                    )
                return None

            def load_manifest(
                self, content: Manifest, storage: object
            ) -> Sequence[NodeDefinition]:
                return []

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = agent_session

            def normalize(self, raw_label: str) -> Node:
                return Node(unit_address=raw_label)

            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("test/pkg")

        class MockDagStorage(DagStorage, Singleton):
            tier = system

            def get_messages(self, node: Node) -> Set[Message]:
                msgs: Set[Message] = {Feedback(content="Fix type error")}
                return msgs

        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register(MockRoleConfig, keys=[RoleConfig], phase=agent_session)
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])
        reg.register(MockDagStorage, keys=[DagStorage])

        with enter_phase(system, registry=reg) as sys_scope:
            with enter_phase(agent_session, registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)
                alias_mgr = scope.get_singleton(AliasManager)

                # Requirement: The session feedback combining feedback messages retrieved from graph storage across the active nodes.
                # Requirement: [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.
                self.assertEqual(cfg.feedback, ("Fix type error",))
                # Requirement: The session template parameters combining template parameters across the active nodes.
                # Requirement: [NodeConfig] The node config provides the session template parameters, providing parameter bindings for template evaluation.
                self.assertEqual(
                    cfg.template_parameters,
                    {"module_name": "MyModule", "has_ops": True},
                )

                # Requirement: The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.
                # Requirement: [NodeConfig] The node config provides the session read-write files permitted for inspection and modification.
                rw_names = {f.relative_path for f in cfg.read_write_files}
                self.assertIn("test/pkg/impl.py", rw_names)
                self.assertIn("test/pkg/internal.py", rw_names)

                # Requirement: The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.
                # Requirement: [NodeConfig] The node config provides the session read-only files restricted to inspection.
                ro_names = {f.relative_path for f in cfg.read_only_files}
                self.assertIn("test/pkg/dep_target.py", ro_names)
                self.assertIn("test/pkg/star_parent.py", ro_names)
                self.assertIn("test/pkg/star_transitive.py", ro_names)

                # Requirement: The session blame targets aggregating blame targets across the active nodes, and blame targets by node mapping each active node to its declared blame targets.
                # Requirement: [NodeConfig] The node config provides blame targets eligible for defect attribution.
                blame_names = {f.relative_path for f in cfg.blame_targets}
                self.assertIn("test/pkg/dep_target.py", blame_names)

                # Requirement: The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.
                # Requirement: [NodeConfig] The node config provides the session verification checks evaluated during session advancement.
                self.assertEqual(len(cfg.verification_checks), 1)
                passed, diag = cfg.verification_checks[0].verify()
                self.assertTrue(passed)
                self.assertEqual(diag.strip(), "verified")

                # Requirement: The alias manager converts relative paths to matching file aliases, producing unbound files when unmapped.
                # Requirement: [AliasManager] Converting a wire type string produces the matching file alias if its relative path is found, and produces an unbound file if the relative path is not found.
                alias_impl = alias_mgr.convert("test/pkg/impl.py")
                self.assertIsInstance(alias_impl, ReadWriteFile)
                self.assertEqual(alias_impl.relative_path, "test/pkg/impl.py")

                alias_dep = alias_mgr.convert("test/pkg/dep_target.py")
                self.assertIsInstance(alias_dep, ReadOnlyFile)
                self.assertEqual(alias_dep.relative_path, "test/pkg/dep_target.py")

                # Sanitize text via lifecycle initialization
                diag_output = (
                    "Verification failed: /sandbox/execroot/_main/test/pkg/impl.py:5: error: syntax\n"
                    "test/pkg/dep_target.py:12: error: missing import"
                )
                sanitized = alias_mgr.sanitize_text(diag_output)
                # Requirement: The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its relative path, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking, stripping workspace root path prefixes, and stripping execution root path prefixes.
                # Requirement: [AliasManager] Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with the corresponding file alias relative paths.
                self.assertEqual(
                    sanitized,
                    "Verification failed: test/pkg/impl.py:5: error: syntax\n"
                    "test/pkg/dep_target.py:12: error: missing import",
                )
                ws_diag = f"ERROR: {alias_mgr.workspace_root.path}/testing/parts/core/lib/BUILD.bazel: no such target"
                self.assertEqual(
                    alias_mgr.sanitize_text(ws_diag),
                    "ERROR: testing/parts/core/lib/BUILD.bazel: no such target",
                )

    def test_lifecycle_initialization_step_mode_disabled(self) -> None:
        """CUJ: When allows_step_mode is false, step mode is disabled and guide is kept as read-only file."""

        class MockManifestLoader(BazelManifestLoader, Singleton):
            tier = agent_session

            def get_manifest(self, node: Node) -> Optional[Manifest]:
                if node.unit_address == "//test/pkg:my_target":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "impl.py",
                                "guide": "//update_python_with_ai/guides:qa",
                                "allows_step_mode": False,
                                "deps": ["//update_python_with_ai/guides:qa"],
                            }
                        )
                    )
                return None

            def load_manifest(
                self, content: Manifest, storage: object
            ) -> Sequence[NodeDefinition]:
                return []

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = agent_session

            def normalize(self, raw_label: str) -> Node:
                return Node(unit_address=raw_label)

            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("test/pkg")

        class MockDagStorage(DagStorage, Singleton):
            tier = system

            def get_messages(self, node: Node) -> Set[Message]:
                return set()

        class MockAgentConfig(AgentConfig, Singleton):
            tier = system

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
        reg.register(MockRoleConfig, keys=[RoleConfig], phase=agent_session)
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])
        reg.register(MockDagStorage, keys=[DagStorage])
        reg.register(MockAgentConfig, keys=[AgentConfig])

        with enter_phase(system, registry=reg) as sys_scope:
            with enter_phase(agent_session, registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)
                alias_mgr = scope.get_singleton(AliasManager)

                # Requirement: Whether the node allows step mode resolved when the session contains exactly one node.
                # Requirement: [NodeConfig] The node config indicates whether the node allows step mode.
                self.assertFalse(cfg.allows_step_mode)
                # Requirement: Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.
                # Requirement: [NodeConfig] The node config indicates whether session step mode is active.
                self.assertFalse(cfg.is_step_mode)
                self.assertIsNone(cfg.guide_file)
                self.assertIsNone(cfg.guide)

                # Guide target is included in read_only_files
                ro_names = {f.relative_path for f in cfg.read_only_files}
                self.assertIn("test/pkg/qa.md", ro_names)

                alias = alias_mgr.convert("test/pkg/qa.md")
                self.assertIsInstance(alias, ReadOnlyFile)

    def test_lifecycle_initialization_step_mode_disabled_when_feedback_present(
        self,
    ) -> None:
        """CUJ: When session feedback is present, step mode is disabled even if agent_config and node allow it, and guide is kept as read-only file."""

        class MockManifestLoader(BazelManifestLoader, Singleton):
            tier = agent_session

            def get_manifest(self, node: Node) -> Optional[Manifest]:
                if node.unit_address == "//test/pkg:my_target":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "impl.py",
                                "guide": "//update_python_with_ai/guides:qa",
                                "allows_step_mode": True,
                                "deps": ["//update_python_with_ai/guides:qa"],
                            }
                        )
                    )
                return None

            def load_manifest(
                self, content: Manifest, storage: object
            ) -> Sequence[NodeDefinition]:
                return []

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = agent_session

            def normalize(self, raw_label: str) -> Node:
                return Node(unit_address=raw_label)

            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("test/pkg")

        class MockDagStorage(DagStorage, Singleton):
            tier = system

            def get_messages(self, node: Node) -> Set[Message]:
                return {Feedback(content="Fix failing mock test")}

        class MockAgentConfig(AgentConfig, Singleton):
            tier = system

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
        reg.register(MockRoleConfig, keys=[RoleConfig], phase=agent_session)
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])
        reg.register(MockDagStorage, keys=[DagStorage])
        reg.register(MockAgentConfig, keys=[AgentConfig])

        with enter_phase(system, registry=reg) as sys_scope:
            with enter_phase(agent_session, registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)
                alias_mgr = scope.get_singleton(AliasManager)

                # Requirement: Whether the node allows step mode resolved when the session contains exactly one node.
                # Requirement: [NodeConfig] The node config indicates whether the node allows step mode.
                self.assertTrue(cfg.allows_step_mode)
                self.assertEqual(cfg.feedback, ("Fix failing mock test",))
                # Requirement: Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.
                # Requirement: [NodeConfig] The node config indicates whether session step mode is active.
                self.assertFalse(cfg.is_step_mode)
                self.assertIsNone(cfg.guide_file)
                self.assertIsNone(cfg.guide)

                # Declared guide dependencies are excluded from read-only files when step mode is active, and included as read-only files when step mode is inactive.
                ro_names = {f.relative_path for f in cfg.read_only_files}
                self.assertIn("test/pkg/qa.md", ro_names)

                alias = alias_mgr.convert("test/pkg/qa.md")
                self.assertIsInstance(alias, ReadOnlyFile)

    @patch("update_with_ai.parts.bazel.lib.bazel_node_config_impl.subprocess.run")
    def test_command_verification_check_stderr_and_errors(
        self, mock_run: MagicMock
    ) -> None:
        """CUJ: _CommandVerificationCheck handles stderr output, combined output, and subprocess errors."""
        check = _CommandVerificationCheck(command="test_cmd", cwd="/tmp")

        # Stderr only on failure
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="compilation error"
        )
        passed, diag = check.verify()
        # Requirement: The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.
        # Requirement: [NodeConfig] The node config provides the session verification checks evaluated during session advancement.
        self.assertFalse(passed)
        self.assertEqual(diag, "compilation error")

        # Stdout and Stderr together
        mock_run.return_value = MagicMock(
            returncode=0, stdout="some warning", stderr="non-fatal warning"
        )
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
        """CUJ: NodeConfig.initialize handles missing RoleConfig, missing/failing DagStorage, and missing/invalid manifest."""
        # 1. RoleConfig missing -> returns early without error
        reg1 = LifecycleRegistry()
        __initialize__(reg1)
        with enter_phase(agent_session, registry=reg1) as scope:
            cfg = scope.get_singleton(NodeConfig)
            self.assertEqual(cfg.read_write_files, set())

        # 1.5 RoleConfig empty -> returns early without error
        class MockRoleConfigEmpty(RoleConfig, Singleton):
            tier = agent_session

            @property
            def role(self) -> str:
                return "coder"

            @property
            def nodes(self) -> Sequence[Node]:
                return ()

            @property
            def version(self) -> int:
                return 1

        reg1_empty = LifecycleRegistry()
        __initialize__(reg1_empty)
        reg1_empty.register(MockRoleConfigEmpty, keys=[RoleConfig], phase=agent_session)
        with enter_phase(agent_session, registry=reg1_empty) as scope:
            cfg = scope.get_singleton(NodeConfig)
            self.assertEqual(cfg.read_write_files, set())

        # 2. DagStorage missing / failing -> self._feedback = ()
        class MockRoleConfigTgt(RoleConfig, Singleton):
            tier = agent_session

            @property
            def role(self) -> str:
                return "coder"

            @property
            def nodes(self) -> Sequence[Node]:
                return (Node(unit_address="//pkg:tgt"),)

            @property
            def version(self) -> int:
                return 1

        class MockManifestLoaderNone(BazelManifestLoader, Singleton):
            tier = agent_session

            def get_manifest(self, node: Node) -> Optional[Manifest]:
                return None

            def load_manifest(
                self, content: Manifest, storage: object
            ) -> Sequence[NodeDefinition]:
                return []

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = agent_session

            def normalize(self, raw_label: str) -> Node:
                return Node(unit_address=raw_label)

            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("pkg")

        reg2 = LifecycleRegistry()
        __initialize__(reg2)
        reg2.register(MockRoleConfigTgt, keys=[RoleConfig], phase=agent_session)
        reg2.register(MockManifestLoaderNone, keys=[BazelManifestLoader])
        reg2.register(MockNodeIdentifierUtility, keys=[BazelTarget])

        with enter_phase(agent_session, registry=reg2) as scope:
            cfg = scope.get_singleton(NodeConfig)
            # Requirement: The session feedback combining feedback messages retrieved from graph storage across the active nodes.
            # Requirement: [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.
            self.assertEqual(cfg.feedback, ())
            # Manifest is None -> returns early
            self.assertEqual(cfg.read_write_files, set())

        # 3. Manifest is invalid JSON -> returns early
        class MockManifestLoaderBadJson(BazelManifestLoader, Singleton):
            tier = agent_session

            def get_manifest(self, node: Node) -> Optional[Manifest]:
                return Manifest("invalid JSON {")

            def load_manifest(
                self, content: Manifest, storage: object
            ) -> Sequence[NodeDefinition]:
                return []

        reg3 = LifecycleRegistry()
        __initialize__(reg3)
        reg3.register(MockRoleConfigTgt, keys=[RoleConfig], phase=agent_session)
        reg3.register(MockManifestLoaderBadJson, keys=[BazelManifestLoader])
        reg3.register(MockNodeIdentifierUtility, keys=[BazelTarget])

        with enter_phase(agent_session, registry=reg3) as scope:
            cfg = scope.get_singleton(NodeConfig)
            self.assertEqual(cfg.read_write_files, set())

    def test_template_resolution_and_parameters_and_verification_message(self) -> None:
        """CUJ: Loading template content across candidate paths, handling JSON string parameters, and verification success message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "template.py")
            with open(template_path, "w", encoding="utf-8") as f:
                f.write("# Template code\n")

            class MockRoleConfigPkg(RoleConfig, Singleton):
                tier = agent_session

                @property
                def role(self) -> str:
                    return "coder"

                @property
                def nodes(self) -> Sequence[Node]:
                    return (Node(unit_address="//pkg:my_target"),)

                @property
                def version(self) -> int:
                    return 1

            class MockManifestLoader(BazelManifestLoader, Singleton):
                tier = agent_session

                def get_manifest(self, node: Node) -> Optional[Manifest]:
                    return Manifest(
                        json.dumps(
                            {
                                "src": "impl.py",
                                "template": template_path,
                                "template_parameters": json.dumps({"key": "value"}),
                                "verification_success_message": "Build passed successfully",
                            }
                        )
                    )

                def load_manifest(
                    self, content: Manifest, storage: object
                ) -> Sequence[NodeDefinition]:
                    return []

            class MockNodeIdentifierUtility(BazelTarget, Singleton):
                tier = agent_session

                def normalize(self, raw_label: str) -> Node:
                    return Node(unit_address=raw_label)

                def extract_directory(self, node: Node) -> NodeDirectory:
                    return _make_node_directory("pkg")

            reg = LifecycleRegistry()
            __initialize__(reg)
            reg.register(MockRoleConfigPkg, keys=[RoleConfig], phase=agent_session)
            reg.register(MockManifestLoader, keys=[BazelManifestLoader])
            reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])

            with enter_phase(agent_session, registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)

                # Requirement: The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.
                # Requirement: [NodeConfig] The node config provides templates mapping read-write files to initial file content.
                self.assertEqual(len(cfg.templates), 1)
                for bound_f, content in cfg.templates:
                    self.assertEqual(bound_f.relative_path, "pkg/impl.py")
                    self.assertEqual(content, "# Template code\n")

                # Requirement: The session template parameters combining template parameters across the active nodes.
                # Requirement: [NodeConfig] The node config provides the session template parameters, providing parameter bindings for template evaluation.
                self.assertEqual(cfg.template_parameters, {"key": "value"})

                # Requirement: The session verification success message from the active node when the session contains exactly one node.
                # Requirement: [NodeConfig] The node config provides the session verification success message when configured.
                self.assertEqual(
                    cfg.verification_success_message, "Build passed successfully"
                )

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

            class MockRoleConfigPkg(RoleConfig, Singleton):
                tier = agent_session

                @property
                def role(self) -> str:
                    return "coder"

                @property
                def nodes(self) -> Sequence[Node]:
                    return (Node(unit_address="//pkg:my_target"),)

                @property
                def version(self) -> int:
                    return 1

            class MockManifestLoader(BazelManifestLoader, Singleton):
                tier = agent_session

                def get_manifest(self, node: Node) -> Optional[Manifest]:
                    return Manifest(
                        json.dumps(
                            {
                                "src": "impl.py",
                                "template": template_path,
                                "template_parameters": "not valid json {",
                                "guide": "//update_python_with_ai/guides:my_guide",
                                "allows_step_mode": True,
                            }
                        )
                    )

                def load_manifest(
                    self, content: Manifest, storage: object
                ) -> Sequence[NodeDefinition]:
                    return []

            class MockNodeIdentifierUtility(BazelTarget, Singleton):
                tier = agent_session

                def normalize(self, raw_label: str) -> Node:
                    return Node(unit_address=raw_label)

                def extract_directory(self, node: Node) -> NodeDirectory:
                    return _make_node_directory("pkg")

            class MockAgentConfig(AgentConfig, Singleton):
                tier = system

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
            reg.register(MockRoleConfigPkg, keys=[RoleConfig], phase=agent_session)
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
                    with enter_phase(system, registry=reg) as sys_scope:
                        with enter_phase(agent_session, registry=reg) as scope:
                            cfg = scope.get_singleton(NodeConfig)
                            # Template read failure results in empty templates
                            # Requirement: The node config exposes templates mapping read-write files to initial file content.
                            # Requirement: [NodeConfig] The node config provides templates mapping read-write files to initial file content.
                            self.assertEqual(cfg.templates, set())
                            # Invalid JSON param string results in default empty dict
                            # Requirement: The node config exposes declared template parameters from the target node manifests.
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
        self.assertEqual(
            parsed_guide.verification_failure, "Review error diagnostics and retry."
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            guides_dir = os.path.join(tmpdir, "update_python_with_ai", "guides")
            os.makedirs(guides_dir, exist_ok=True)
            guide_file_path = os.path.join(guides_dir, "my_guide.md")
            with open(guide_file_path, "w", encoding="utf-8") as f:
                f.write(guide_content)

            class MockRoleConfigPkg(RoleConfig, Singleton):
                tier = agent_session

                @property
                def role(self) -> str:
                    return "coder"

                @property
                def nodes(self) -> Sequence[Node]:
                    return (Node(unit_address="//pkg:my_target"),)

                @property
                def version(self) -> int:
                    return 1

            class MockManifestLoader(BazelManifestLoader, Singleton):
                tier = agent_session

                def get_manifest(self, node: Node) -> Optional[Manifest]:
                    return Manifest(
                        json.dumps(
                            {
                                "src": "impl.py",
                                "guide": "my_guide",
                                "allows_step_mode": True,
                                "deps": ["my_guide"],
                            }
                        )
                    )

                def load_manifest(
                    self, content: Manifest, storage: object
                ) -> Sequence[NodeDefinition]:
                    return []

            class MockNodeIdentifierUtility(BazelTarget, Singleton):
                tier = agent_session

                def normalize(self, raw_label: str) -> Node:
                    return Node(unit_address=raw_label)

                def extract_directory(self, node: Node) -> NodeDirectory:
                    return _make_node_directory("pkg")

            class MockAgentConfig(AgentConfig, Singleton):
                tier = system

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
            reg.register(MockRoleConfigPkg, keys=[RoleConfig], phase=agent_session)
            reg.register(MockManifestLoader, keys=[BazelManifestLoader])
            reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])
            reg.register(MockAgentConfig, keys=[AgentConfig])

            old_env = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            try:
                os.environ["BUILD_WORKSPACE_DIRECTORY"] = tmpdir
                with enter_phase(system, registry=reg) as sys_scope:
                    with enter_phase(agent_session, registry=reg) as scope:
                        cfg = scope.get_singleton(NodeConfig)
                        alias_mgr = scope.get_singleton(AliasManager)

                        # Requirement: Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.
                        # Requirement: [NodeConfig] The node config indicates whether session step mode is active.
                        self.assertTrue(cfg.is_step_mode)

                        # Requirement: The session guide file and task guide from the single active node when guide step mode is active.
                        # Requirement: [NodeConfig] The node config provides the session guide file when step mode is active.
                        self.assertIsNotNone(cfg.guide_file)
                        assert cfg.guide_file is not None
                        self.assertEqual(cfg.guide_file.relative_path, "my_guide.md")

                        # Requirement: The session guide file and task guide from the single active node when guide step mode is active.
                        # Requirement: [NodeConfig] The node config provides the session guide, providing structured instructional text when step mode is active.
                        self.assertIsNotNone(cfg.guide)
                        assert cfg.guide is not None
                        self.assertEqual(
                            cfg.guide.summary, "This is the summary of the task."
                        )
                        self.assertEqual(len(cfg.guide.sections), 2)
                        self.assertEqual(
                            cfg.guide.verification_failure,
                            "Review error diagnostics and retry.",
                        )

                        # Guide is excluded from read_only_files when step mode is active
                        # Requirement: The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.
                        # Requirement: [NodeConfig] The node config provides the session read-only files restricted to inspection.
                        ro_names = {f.relative_path for f in cfg.read_only_files}
                        self.assertNotIn("my_guide.md", ro_names)

                        # Guide file is registered in AliasManager
                        # Requirement: The alias manager converts relative paths to matching file aliases, producing unbound files when unmapped.
                        # Requirement: [AliasManager] Converting a wire type string produces the matching file alias if its relative path is found, and produces an unbound file if the relative path is not found.
                        converted_guide = alias_mgr.convert("my_guide.md")
                        self.assertEqual(converted_guide, cfg.guide_file)
            finally:
                if old_env is not None:
                    os.environ["BUILD_WORKSPACE_DIRECTORY"] = old_env
                else:
                    os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)

    def test_dependency_resolution_branches(self) -> None:
        """CUJ: Resolving star_deps with diamond graphs, invalid JSON, silent_deps, and manifest-less specs/other dependencies."""

        class MockRoleConfigRoot(RoleConfig, Singleton):
            tier = agent_session

            @property
            def role(self) -> str:
                return "coder"

            @property
            def nodes(self) -> Sequence[Node]:
                return (Node(unit_address="//pkg:root"),)

            @property
            def version(self) -> int:
                return 1

        class MockManifestLoader(BazelManifestLoader, Singleton):
            tier = agent_session

            def get_manifest(self, node: Node) -> Optional[Manifest]:
                if node.unit_address == "//pkg:root":
                    return Manifest(
                        json.dumps(
                            {
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
                            }
                        )
                    )
                if node.unit_address == "//pkg:star_a":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "star_a.py",
                                "star_deps": [
                                    "//pkg:star_diamond",
                                    "//pkg:star_bad_json",
                                ],
                            }
                        )
                    )
                if node.unit_address == "//pkg:star_b":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "star_b.py",
                                "star_deps": ["//pkg:star_diamond"],
                            }
                        )
                    )
                if node.unit_address == "//pkg:star_diamond":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "star_diamond.py",
                            }
                        )
                    )
                if node.unit_address == "//pkg:star_bad_json":
                    return Manifest("not valid json {")
                if node.unit_address == "//pkg:bad_json_dep":
                    return Manifest("not valid json {")
                return None

            def load_manifest(
                self, content: Manifest, storage: object
            ) -> Sequence[NodeDefinition]:
                return []

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = agent_session

            def normalize(self, raw_label: str) -> Node:
                return Node(unit_address=raw_label)

            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("pkg")

        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register(MockRoleConfigRoot, keys=[RoleConfig], phase=agent_session)
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])

        with enter_phase(agent_session, registry=reg) as scope:
            cfg = scope.get_singleton(NodeConfig)

            # Requirement: The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.
            # Requirement: [NodeConfig] The node config provides the session read-only files restricted to inspection.
            ro_names = {f.relative_path for f in cfg.read_only_files}
            self.assertNotIn("pkg/silent_dep.py", ro_names)
            self.assertIn("pkg/star_a.py", ro_names)
            self.assertIn("pkg/star_b.py", ro_names)
            self.assertIn("pkg/star_diamond.py", ro_names)
            self.assertIn("pkg/grounding/foo.pyi", ro_names)
            self.assertIn("pkg/grounding/bar_grounding.pyi", ro_names)
            self.assertIn("pkg/high/baz.md", ro_names)
            self.assertIn("pkg/util.py", ro_names)

    def test_lifecycle_initialization_multi_node_batch(self) -> None:
        """CUJ: Multi-node batch initialization unifies read-write files, excludes in-batch read-write files from read-only files, per-node blame targets, disables step mode, and per-node verification checks."""
        node_a = Node(unit_address="//pkg:node_a")
        node_b = Node(unit_address="//pkg:node_b")
        node_c = Node(unit_address="//pkg:node_c")

        class MockMultiRoleConfig(RoleConfig, Singleton):
            tier = agent_session

            @property
            def role(self) -> str:
                return "coder"

            @property
            def nodes(self) -> Sequence[Node]:
                return (node_a, node_b, node_c)

            @property
            def version(self) -> int:
                return 1

        class MockManifestLoader(BazelManifestLoader, Singleton):
            tier = agent_session

            def get_manifest(self, node: Node) -> Optional[Manifest]:
                if node.unit_address == "//pkg:node_a":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "pkg/a.py",
                                "template": "nonexistent_template.py",
                                "allows_step_mode": True,
                                "verify": "echo verify_a",
                            }
                        )
                    )
                if node.unit_address == "//pkg:node_b":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "b.py",
                                "deps": ["//pkg:node_a", "//pkg:ext_dep"],
                                "feedback_deps": ["//pkg:node_a", "//pkg:ext_dep"],
                                "verify": "echo verify_b",
                            }
                        )
                    )
                if node.unit_address == "//pkg:ext_dep":
                    return Manifest(
                        json.dumps(
                            {
                                "src": "pkg/ext.py",
                            }
                        )
                    )
                return None

            def load_manifest(
                self, content: Manifest, storage: object
            ) -> Sequence[NodeDefinition]:
                return []

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = agent_session

            def normalize(self, raw_label: str) -> Node:
                return Node(unit_address=raw_label)

            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("pkg")

        class MockAgentConfig(AgentConfig, Singleton):
            tier = system

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
        reg.register(MockMultiRoleConfig, keys=[RoleConfig], phase=agent_session)
        reg.register(MockManifestLoader, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])
        reg.register(MockAgentConfig, keys=[AgentConfig])

        with enter_phase(system, registry=reg) as sys_scope:
            with enter_phase(agent_session, registry=reg) as scope:
                cfg = scope.get_singleton(NodeConfig)
                alias_mgr = scope.get_singleton(AliasManager)

                # Requirement: The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.
                # Requirement: [NodeConfig] The node config provides the session read-write files permitted for inspection and modification.
                rw_names = {f.relative_path for f in cfg.read_write_files}
                self.assertEqual(rw_names, {"pkg/a.py", "pkg/b.py"})

                # Requirement: The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.
                # Requirement: [NodeConfig] The node config provides the session read-only files restricted to inspection.
                ro_names = {f.relative_path for f in cfg.read_only_files}
                # a.py is an in-batch read-write file, so it MUST NOT be in read_only_files!
                self.assertEqual(ro_names, {"pkg/ext.py"})

                # Requirement: Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.
                # Requirement: [NodeConfig] The node config indicates whether session step mode is active.
                self.assertFalse(cfg.is_step_mode)
                self.assertFalse(cfg.allows_step_mode)
                self.assertIsNone(cfg.verification_success_message)

                # Requirement: The session blame targets aggregating blame targets across the active nodes, and blame targets by node mapping each active node to its declared blame targets.
                # Requirement: [NodeConfig] The node config provides the session blame targets mapped by session node.
                blame_by_node = cfg.blame_targets_by_node
                self.assertEqual(blame_by_node[node_a], set())
                node_b_blames = {f.relative_path for f in blame_by_node[node_b]}
                self.assertEqual(node_b_blames, {"pkg/a.py", "pkg/ext.py"})

                # Requirement: The session blame targets aggregating blame targets across the active nodes, and blame targets by node mapping each active node to its declared blame targets.
                # Requirement: [NodeConfig] The node config provides blame targets eligible for defect attribution.
                self.assertEqual(
                    {f.relative_path for f in cfg.blame_targets}, {"pkg/a.py", "pkg/ext.py"}
                )

                # Requirement: The session src file alias by node mapping each active node to the relative path of its declared source file alias.
                # Requirement: [NodeConfig] The node config provides the source file alias relative path mapped by session node.
                self.assertEqual(cfg.src_file_alias_by_node[node_a], "pkg/a.py")
                self.assertEqual(cfg.src_file_alias_by_node[node_b], "pkg/b.py")

                # Requirement: The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.
                # Requirement: [NodeConfig] The node config provides the session verification checks mapped by session node.
                self.assertEqual(len(cfg.verification_checks_by_node[node_a]), 1)
                self.assertEqual(len(cfg.verification_checks_by_node[node_b]), 1)

                # Requirement: The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.
                # Requirement: [NodeConfig] The node config provides the session verification checks evaluated during session advancement.
                self.assertEqual(len(cfg.verification_checks), 2)

    def test_node_config_per_node_info_cache_and_eviction(self) -> None:
        """CUJ: NodeConfig caches PerNodeInfo, unloads on version increment when nodes leave, and aggregates dynamically."""
        node_1 = Node(unit_address="//pkg:node_1")
        node_2 = Node(unit_address="//pkg:node_2")
        node_3 = Node(unit_address="//pkg:node_3")

        manifests = {
            "//pkg:node_1": Manifest(json.dumps({"src": "pkg/one.py"})),
            "//pkg:node_2": Manifest(json.dumps({"src": "pkg/two.py"})),
            "//pkg:node_3": Manifest(json.dumps({"src": "pkg/three.py"})),
        }

        call_counts = {"//pkg:node_1": 0, "//pkg:node_2": 0, "//pkg:node_3": 0}

        class MockManifestLoaderCounting(BazelManifestLoader, Singleton):
            tier = agent_session

            def get_manifest(self, node: Node) -> Optional[Manifest]:
                addr = node.unit_address
                if addr in call_counts:
                    call_counts[addr] += 1
                return manifests.get(addr)

            def load_manifest(
                self, content: Manifest, storage: object
            ) -> Sequence[NodeDefinition]:
                return []

        class MockNodeIdentifierUtility(BazelTarget, Singleton):
            tier = agent_session

            def normalize(self, raw_label: str) -> Node:
                return Node(unit_address=raw_label)

            def extract_directory(self, node: Node) -> NodeDirectory:
                return _make_node_directory("pkg")

        reg = LifecycleRegistry()
        __initialize__(reg)
        reg.register(MockRoleConfig, keys=[RoleConfig], phase=agent_session)
        reg.register(MockManifestLoaderCounting, keys=[BazelManifestLoader])
        reg.register(MockNodeIdentifierUtility, keys=[BazelTarget])

        with enter_phase(agent_session, registry=reg) as scope:
            cfg = scope.get_singleton(NodeConfig)
            role_cfg = scope.get_singleton(RoleConfig)
            assert isinstance(role_cfg, MockRoleConfig)

            # Step 1: Start with node_1
            role_cfg.set_nodes([node_1])
            # Requirement: The session per node info by node mapping each active node to its per node info.
            # Requirement: [NodeConfig] The node config provides the session per node info by node, mapping each active node to its per node info.
            self.assertIn(node_1, cfg.per_node_info_by_node)
            self.assertEqual(call_counts["//pkg:node_1"], 1)
            rw_1 = {f.relative_path for f in cfg.read_write_files}
            self.assertEqual(rw_1, {"pkg/one.py"})

            # Step 2: Querying again without version change does not re-fetch
            _ = cfg.read_write_files
            self.assertEqual(call_counts["//pkg:node_1"], 1)

            # Step 3: Change active nodes to node_2 (node_1 is removed, version incremented)
            role_cfg.set_nodes([node_2])
            # Requirement: The session per node info by node mapping each active node to its per node info.
            # Requirement: [NodeConfig] The node config provides the session per node info by node, mapping each active node to its per node info.
            self.assertNotIn(node_1, cfg.per_node_info_by_node)
            self.assertIn(node_2, cfg.per_node_info_by_node)
            self.assertEqual(call_counts["//pkg:node_2"], 1)
            rw_2 = {f.relative_path for f in cfg.read_write_files}
            self.assertEqual(rw_2, {"pkg/two.py"})

            # Step 4: Expand active nodes to [node_2, node_3] (node_2 is cached, node_3 is loaded)
            role_cfg.set_nodes([node_2, node_3])
            rw_multi = {f.relative_path for f in cfg.read_write_files}
            # node_2 was cached, not re-fetched
            self.assertEqual(call_counts["//pkg:node_2"], 1)
            self.assertEqual(call_counts["//pkg:node_3"], 1)
            self.assertEqual(rw_multi, {"pkg/two.py", "pkg/three.py"})
            self.assertIn(node_2, cfg.per_node_info_by_node)
            self.assertIn(node_3, cfg.per_node_info_by_node)

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
            tier=agent_session,
        )
        with enter_phase(agent_session, registry=reg) as scope:
            alias_mgr = scope.get_singleton(AliasManager)
            assert isinstance(alias_mgr, AliasManagerImpl)
            self.assertEqual(len(alias_mgr._aliases), 0)

        # 3. sanitize_text direct path fallback
        assert isinstance(alias_mgr, AliasManagerImpl)
        alias_mgr._paths["/non_regex_matched/custom_path.py"] = "custom_path.py"
        text = "Path without word boundary: [/non_regex_matched/custom_path.py]"
        sanitized = alias_mgr.sanitize_text(text)
        # Requirement: The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its relative path, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking, stripping workspace root path prefixes, and stripping execution root path prefixes.
        # Requirement: [AliasManager] Sanitizing text masks occurrences of relative workspace paths and preceding path prefixes with the corresponding file alias short names.
        self.assertEqual(sanitized, "Path without word boundary: [custom_path.py]")


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
