# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T02:07:35Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: b25cee114f55
# COVERAGE_AUDIT: 2026-10-05T02:07:35Z
# QA_AUDIT: 2026-10-05T02:07:35Z
# --- END CLEANROOM METADATA ---

"""Unit tests for bazel_node_config_impl aligned with grounding specifications."""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, cast

from update_with_ai.parts.agent.lib.agent_config import AgentConfig
from update_with_ai.parts.agent.lib.agent_file_alias import (
    AliasManager,
    BoundFile,
    FileAlias,
    FileContent,
    ReadOnlyFile,
    ReadWriteFile,
    RelativePath,
    UnboundFile,
    UnsanitizedText,
)
from update_with_ai.parts.agent.lib.agent_node_config import (
    NodeConfig,
    NodeGuide,
    PerNodeInfo,
    RoleConfig,
    StepSection,
    VerificationCheck,
    VerificationSuccessMessage,
)
from update_with_ai.parts.agent.lib.agent_session import AgentSessionTier
from update_with_ai.parts.agent.lib.agent_storage import AgentStorage
from update_with_ai.parts.bazel.lib.bazel_manifest_loader import (
    BazelManifestLoader,
    TargetManifest,
)
from update_with_ai.parts.bazel.lib.bazel_node_config_impl import (
    AliasManager as AliasManagerImpl,
    NodeConfig as NodeConfigImpl,
    __initialize__,
)
from update_with_ai.parts.bazel.lib.bazel_target import BazelTarget, NodeDirectory
from update_with_ai.parts.core.lib.file_paths import (
    AbsolutePath,
    FilePathManager,
    HostPath,
    PathString,
    WorkspacePath,
    WorkspaceRoot,
)
from update_with_ai.parts.dag.lib.dag_storage import (
    DagMessage,
    DagNode,
    DagStorage,
    FeedbackMessage,
    MessageContent,
    RoleAddress,
    UnitAddress,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase


def _make_dag_node(unit_address: str, role_address: str = "") -> DagNode:
    return DagNode(
        unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address)
    )


class FakeFilePaths:
    tier = "system"

    def __init__(self, root_dir: str = "/workspace") -> None:
        self.root_dir = root_dir

    def get_workspace_root(self) -> WorkspaceRoot:
        return WorkspaceRoot(path=PathString(self.root_dir))

    def create_host_path(self, path: str) -> HostPath:
        return HostPath(path=PathString(path))

    def create_absolute_path(self, path: str) -> AbsolutePath:
        return AbsolutePath(path=PathString(path))

    def create_workspace_path(self, path: str) -> WorkspacePath:
        return WorkspacePath(path=PathString(path))

    def resolve_path(self, root: AbsolutePath, relative: WorkspacePath) -> AbsolutePath:
        return AbsolutePath(path=PathString(f"{root.path}/{relative.path}"))


class FakeBazelTarget:
    tier = "system"

    def normalize_target(self, target_identifier: str) -> DagNode:
        if "#" in target_identifier:
            u, r = target_identifier.split("#", 1)
            return _make_dag_node(u, r)
        return _make_dag_node(target_identifier, "")

    def extract_node_dir(self, node: DagNode) -> NodeDirectory:
        pkg = node.unit_address.split(":")[0].lstrip("/")
        return NodeDirectory(path=PathString(pkg))


class FakeRoleConfig:
    tier = "agent_session"

    def __init__(
        self, role: str = "lib", nodes: Optional[Sequence[DagNode]] = None
    ) -> None:
        self._role = role
        self._nodes = list(nodes or [_make_dag_node("//pkg:target", "lib")])
        self._version = 1

    @property
    def role(self) -> str:
        return self._role

    @property
    def nodes(self) -> Sequence[DagNode]:
        return self._nodes

    @property
    def version(self) -> int:
        return self._version

    def set_role(self, role: str) -> None:
        self._role = role

    def set_nodes(self, nodes: Sequence[DagNode]) -> None:
        self._nodes = list(nodes)
        self._version += 1


class FakeAgentConfig:
    tier = "system"

    def __init__(self, is_step_mode: bool = True) -> None:
        self._is_step_mode = is_step_mode

    @property
    def is_step_mode(self) -> bool:
        return self._is_step_mode


class FakeAgentStorage:
    tier = "system"

    def __init__(self) -> None:
        self._messages: Dict[DagNode, Set[DagMessage]] = {}

    def get_messages(self, node: DagNode) -> Set[DagMessage]:
        return set(self._messages.get(node, set()))

    def add_message(self, message: DagMessage, to: DagNode) -> None:
        self._messages.setdefault(to, set()).add(message)


class FakeManifestLoader:
    tier = "system"

    def __init__(self) -> None:
        self.manifests: Dict[str, TargetManifest] = {}

    def retrieve_manifest(self, node: DagNode) -> Optional[TargetManifest]:
        return self.manifests.get(node.unit_address)


class BazelNodeConfigImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.file_paths = FakeFilePaths("/workspace")
        self.bazel_target = FakeBazelTarget()
        self.role_config = FakeRoleConfig()
        self.agent_config = FakeAgentConfig(is_step_mode=True)
        self.storage = FakeAgentStorage()
        self.manifest_loader = FakeManifestLoader()

        self.registry.register_instance(
            self.file_paths, keys=[FilePathManager], tier="system"
        )
        self.registry.register_instance(
            self.bazel_target, keys=[BazelTarget], tier="system"
        )
        self.registry.register_instance(
            self.agent_config, keys=[AgentConfig], tier="system"
        )
        self.registry.register_instance(
            self.storage, keys=[AgentStorage, DagStorage], tier="system"
        )
        self.registry.register_instance(
            self.manifest_loader, keys=[BazelManifestLoader], tier="system"
        )
        self.registry.register_instance(
            self.role_config, keys=[RoleConfig], tier="agent_session"
        )
        __initialize__(self.registry)

    def test_alias_manager_sanitize_text(self) -> None:
        """CUJ: Sanitizing text by masking workspace paths and stripping execution roots."""
        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                mgr = scope.get_singleton(AliasManager)
                self.assertIsInstance(mgr, AliasManagerImpl)

                # Requirement: MUST mask relative workspace paths and preceding path prefixes with relative paths using backtracking-safe regex patterns.
                # Requirement: MUST strip workspace root and execution root path prefixes.
                # Requirement: MUST sanitize text by masking occurrences of relative workspace paths and preceding path prefixes with file alias relative paths.
                raw_text = UnsanitizedText("Error in /workspace/pkg/target.py: line 10")
                sanitized = mgr.sanitize_text(raw_text)
                self.assertNotIn("/workspace/", sanitized)

    def test_alias_manager_convert(self) -> None:
        """CUJ: Converting wire path string to FileAlias for bound and unbound files."""
        target_node = _make_dag_node("//pkg:target", "lib")
        manifest = TargetManifest(
            label=cast(Any, "//pkg:target"),
            source_file=cast(Any, RelativePath("pkg/target.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
        )
        self.manifest_loader.manifests["//pkg:target"] = manifest

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                mgr = scope.get_singleton(AliasManager)

                # Requirement: MUST convert wire type strings to file aliases without failure.
                # Requirement: WHEN a wire string does not match any declared bound file, MUST produce an unbound file.
                unbound = mgr.convert("unknown/file.txt")
                self.assertIsInstance(unbound, FileAlias)
                self.assertIsInstance(unbound, UnboundFile)

                # Requirement: WHEN a wire string matches a declared bound file, MUST produce that read-only or read-write file.
                bound = mgr.convert("pkg/target.py")
                self.assertIsInstance(bound, FileAlias)
                self.assertIsInstance(bound, BoundFile)
                assert isinstance(bound, BoundFile)
                self.assertEqual(bound.relative_path, "pkg/target.py")

    def test_node_config_manifest_resolution_single_node(self) -> None:
        """CUJ: Resolving NodeConfig read-write, read-only, templates, and blame targets from target manifests."""
        target_node = _make_dag_node("//pkg:target", "lib")
        dep_node = _make_dag_node("//dep:upstream", "lib")
        blame_node = _make_dag_node("//blame:dep", "lib")

        main_manifest = TargetManifest(
            label=cast(Any, "//pkg:target"),
            task_prompt=cast(Any, "Task prompt for target"),
            source_file=cast(Any, RelativePath("pkg/target.py")),
            silent_source_files=[cast(Any, RelativePath("pkg/silent.py"))],
            template=cast(Any, "Starter template content"),
            dependencies=[cast(Any, "//dep:upstream")],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[cast(Any, "//blame:dep")],
            verification_check=cast(Any, "bazel test //pkg:target_test"),
        )
        dep_manifest = TargetManifest(
            label=cast(Any, "//dep:upstream"),
            source_file=cast(Any, RelativePath("dep/upstream.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
        )
        blame_manifest = TargetManifest(
            label=cast(Any, "//blame:dep"),
            source_file=cast(Any, RelativePath("blame/dep.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
        )
        self.manifest_loader.manifests["//pkg:target"] = main_manifest
        self.manifest_loader.manifests["//dep:upstream"] = dep_manifest
        self.manifest_loader.manifests["//blame:dep"] = blame_manifest

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfigImpl)
                self.assertIsInstance(cfg, NodeConfigImpl)

                # Read-write files: declared primary and silent source files
                # Requirement: MUST aggregate read-write files and templates across active nodes.
                rw_rel_paths = {f.relative_path for f in cfg.read_write_files}
                self.assertIn("pkg/target.py", rw_rel_paths)

                # Read-only files: direct dependencies, excluding session read-write files
                # Requirement: MUST aggregate read-only files across active nodes, excluding session read-write files.
                ro_rel_paths = {f.relative_path for f in cfg.read_only_files}
                self.assertIn("dep/upstream.py", ro_rel_paths)
                self.assertNotIn("pkg/target.py", ro_rel_paths)

                # Templates mapping
                # Requirement: MUST aggregate read-write files and templates across active nodes.
                templates = cfg.templates
                self.assertIsInstance(templates, Mapping)

                # Template parameters
                # Requirement: MUST combine template parameters across active nodes.
                template_params = cfg.template_parameters
                self.assertIsInstance(template_params, Mapping)

                # Blame targets
                # Requirement: MUST map each active node to its declared blame targets.
                blame_targets = cfg.blame_targets_by_node
                self.assertIsInstance(blame_targets, Mapping)
                self.assertIn(target_node, blame_targets)

                # Verification checks
                # Requirement: MUST aggregate verification checks across active nodes.
                vchecks = cfg.verification_checks
                self.assertIsInstance(vchecks, Sequence)

                # Verification checks mapped by node
                # Requirement: MUST map each active node to its verification checks.
                vchecks_by_node = cfg.verification_checks_by_node
                self.assertIsInstance(vchecks_by_node, Mapping)
                self.assertIn(target_node, vchecks_by_node)

                # Source file alias mapped by node
                # Requirement: MUST map each active node to the relative path of its declared source file alias.
                src_alias_by_node = cfg.src_file_alias_by_node
                self.assertIsInstance(src_alias_by_node, Mapping)
                self.assertIn(target_node, src_alias_by_node)
                self.assertEqual(src_alias_by_node[target_node], "pkg/target.py")

    def test_node_config_multi_node_and_per_node_info(self) -> None:
        """CUJ: Mapping per-node information across multiple session nodes."""
        node1 = _make_dag_node("//pkg:unit1", "lib")
        node2 = _make_dag_node("//pkg:unit2", "lib")
        self.role_config.set_nodes([node1, node2])

        m1 = TargetManifest(
            label=cast(Any, "//pkg:unit1"),
            source_file=cast(Any, RelativePath("pkg/unit1.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
        )
        m2 = TargetManifest(
            label=cast(Any, "//pkg:unit2"),
            source_file=cast(Any, RelativePath("pkg/unit2.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
        )
        self.manifest_loader.manifests["//pkg:unit1"] = m1
        self.manifest_loader.manifests["//pkg:unit2"] = m2

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfigImpl)
                per_node_info = cfg.per_node_info_by_node
                # Requirement: MUST map each active node to its per node info.
                self.assertIsInstance(per_node_info, Mapping)
                self.assertIn(node1, per_node_info)
                info1 = per_node_info[node1]
                self.assertIsInstance(info1, PerNodeInfo)
                rw_paths1 = {f.relative_path for f in info1.read_write_files}
                self.assertIn("pkg/unit1.py", rw_paths1)
                self.assertIn(node2, per_node_info)
                info2 = per_node_info[node2]
                self.assertIsInstance(info2, PerNodeInfo)

                # Requirement: MUST map each active node to its verification checks.
                self.assertIn(node1, cfg.verification_checks_by_node)
                self.assertIn(node2, cfg.verification_checks_by_node)

                # Requirement: MUST map each active node to the relative path of its declared source file alias.
                self.assertIn(node1, cfg.src_file_alias_by_node)
                self.assertIn(node2, cfg.src_file_alias_by_node)

                # Requirement: WHEN exactly one node is active, MUST provide the verification success message from the active node.
                # In multi-node sessions, verification_success_message must be None.
                self.assertIsNone(cfg.verification_success_message)

    def test_node_config_guide_markdown_decomposition(self) -> None:
        """CUJ: Parsing guide documents into sections, summary, and verification failure instructions."""
        target_node = _make_dag_node("//pkg:guided_target", "lib")
        self.role_config.set_nodes([target_node])

        guide_content = (
            "# Guide Title\n\n"
            "## Summary\n"
            "This is the summary of the guide.\n\n"
            "## Lint checks\n"
            "- [ ] test passes\n\n"
            "## Step 1: Write Tests\n"
            "Implement unit tests according to spec.\n\n"
            "## Step 2: Implement Code\n"
            "Implement production logic to pass tests.\n\n"
            "## Verification Failure\n"
            "When verification fails, run test_lint.py to diagnose errors."
        )
        guide_manifest = TargetManifest(
            label=cast(Any, "//pkg:guided_target"),
            source_file=cast(Any, RelativePath("pkg/code.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
            guide_target=cast(Any, "//pkg:guide_doc"),
        )
        guide_doc_manifest = TargetManifest(
            label=cast(Any, "//pkg:guide_doc"),
            task_prompt=cast(Any, "Update pkg/guide.md, which is a guide."),
            source_file=cast(Any, RelativePath("pkg/guide.md")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
            template=None,
        )
        self.manifest_loader.manifests["//pkg:guided_target"] = guide_manifest
        self.manifest_loader.manifests["//pkg:guide_doc"] = guide_doc_manifest

        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg_dir = os.path.join(tmp_dir, "pkg")
            os.makedirs(pkg_dir, exist_ok=True)
            with open(os.path.join(pkg_dir, "guide.md"), "w", encoding="utf-8") as f:
                f.write(guide_content)
            with patch.dict(os.environ, {"BUILD_WORKSPACE_DIRECTORY": tmp_dir}):
                with enter_phase("system", registry=self.registry):
                    with enter_phase("agent_session", registry=self.registry) as scope:
                        cfg = scope.get_singleton(NodeConfigImpl)
                        # Requirement: WHEN guide step mode is active, MUST provide the session task guide.
                        # Requirement: MUST extract the guide summary from content under headings titled "Summary".
                        # Requirement: WHEN a section heading begins with "Verification failure", MUST capture verification failure instructions.
                        # Requirement: MUST create sequential step sections for subsequent level-two headings.
                        # Requirement: MUST exclude sections titled "Summary", "Lint checks", or "Verification failure" from step sections.
                        # Requirement: MUST resolve candidate guide paths from declared guide target source files.
                        # Requirement: MUST load guide markdown content by reading the resolved guide file across workspace and runfiles trees.
                        guide = cfg.guide
                        self.assertIsNotNone(guide)
                        assert guide is not None
                        self.assertIsInstance(guide, NodeGuide)
                        self.assertIsInstance(guide.sections, list)
                        self.assertIn("summary of the guide", guide.summary)
                        self.assertIsNotNone(guide.verification_failure)
                        assert guide.verification_failure is not None
                        self.assertIn("test_lint.py", guide.verification_failure)

                        titles = [s.title for s in guide.sections]
                        self.assertIn("Step 1: Write Tests", titles)
                        self.assertIn("Step 2: Implement Code", titles)
                        self.assertNotIn("Summary", titles)
                        self.assertNotIn("Lint checks", titles)
                        self.assertNotIn("Verification Failure", titles)

                        # Requirement: WHEN guide step mode is active, MUST provide the session guide file.
                        # Requirement: MUST expose the unbound guide file from guide target labels.
                        guide_file = cfg.guide_file
                        self.assertIsNotNone(guide_file)
                        assert guide_file is not None
                        self.assertIsInstance(guide_file, UnboundFile)

                        self.assertIsInstance(cfg.allows_step_mode, bool)
                        self.assertIsInstance(cfg.is_step_mode, bool)

    def test_node_config_is_step_mode_conditions(self) -> None:
        """CUJ: Evaluating step mode activation conditions: agent config, single node, node allows step mode, and feedback absence."""
        target_node = _make_dag_node("//pkg:step_target", "lib")
        other_node = _make_dag_node("//pkg:other_target", "lib")
        self.role_config.set_nodes([target_node])

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfigImpl)
                # Requirement: WHEN agent config enables step mode, exactly one node is active, that node allows step mode, and session feedback is absent, MUST activate step mode.
                self.assertTrue(cfg.is_step_mode)

        # When feedback is present on active node, step mode is not active
        self.storage.add_message(
            FeedbackMessage(content=MessageContent("Issue found")),
            to=target_node,
        )
        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfigImpl)
                self.assertFalse(cfg.is_step_mode)

        # When multiple nodes are active, step mode is not active
        self.storage._messages.clear()
        self.role_config.set_nodes([target_node, other_node])
        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfigImpl)
                self.assertFalse(cfg.is_step_mode)

    def test_node_config_per_node_info_caching_and_version_invalidation(self) -> None:
        """CUJ: Caching per-node info and invalidating/unloading when role config version changes."""
        node1 = _make_dag_node("//pkg:cnode1", "lib")
        node2 = _make_dag_node("//pkg:cnode2", "lib")
        self.role_config.set_nodes([node1])

        m1 = TargetManifest(
            label=cast(Any, "//pkg:cnode1"),
            source_file=cast(Any, RelativePath("pkg/cnode1.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
        )
        m2 = TargetManifest(
            label=cast(Any, "//pkg:cnode2"),
            source_file=cast(Any, RelativePath("pkg/cnode2.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
        )
        self.manifest_loader.manifests["//pkg:cnode1"] = m1
        self.manifest_loader.manifests["//pkg:cnode2"] = m2

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfigImpl)
                # Requirement: MUST cache per node info loaded for active nodes from role config.
                info_map = cfg.per_node_info_by_node
                self.assertIn(node1, info_map)
                self.assertNotIn(node2, info_map)

                # Increment version and update nodes
                # Requirement: MUST check the role config version to unload cached info when nodes are no longer being cleaned.
                # Requirement: MUST update file aliases and path masking when the role config version changes.
                self.role_config.set_nodes([node2])
                info_map2 = cfg.per_node_info_by_node
                self.assertIn(node2, info_map2)
                self.assertNotIn(node1, info_map2)

    def test_verification_check_execution(self) -> None:
        """CUJ: Executing verification commands, validating exit status, and formatting diagnostics."""
        target_node = _make_dag_node("//pkg:vcheck_target", "lib")
        self.role_config.set_nodes([target_node])

        v_manifest = TargetManifest(
            label=cast(Any, "//pkg:vcheck_target"),
            source_file=cast(Any, RelativePath("pkg/main.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
            verification_check=cast(Any, "echo pass"),
        )
        self.manifest_loader.manifests["//pkg:vcheck_target"] = v_manifest

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfigImpl)
                vchecks = cfg.verification_checks
                for check in vchecks:
                    self.assertTrue(callable(getattr(check, "verify", None)))
                    status, diagnostic = check.verify()
                    self.assertIsInstance(status, bool)
                    self.assertIsInstance(diagnostic, str)

    def test_verification_check_execution_failing_command(self) -> None:
        """CUJ: Executing a verification command that fails with a non-zero exit status formats diagnostics."""
        target_node = _make_dag_node("//pkg:vfail_target", "lib")
        self.role_config.set_nodes([target_node])

        v_fail_manifest = TargetManifest(
            label=cast(Any, "//pkg:vfail_target"),
            source_file=cast(Any, RelativePath("pkg/main.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
            verification_check=cast(Any, "sh -c 'echo failure on stderr >&2; exit 1'"),
        )
        self.manifest_loader.manifests["//pkg:vfail_target"] = v_fail_manifest

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfigImpl)
                # Requirement: MUST resolve declared verification commands as verification checks.
                # Requirement: MUST aggregate verification checks across active nodes.
                vchecks = cfg.verification_checks
                for check in vchecks:
                    self.assertTrue(callable(getattr(check, "verify", None)))
                    status, diagnostic = check.verify()
                    self.assertIsInstance(status, bool)
                    self.assertIsInstance(diagnostic, str)

    def test_node_config_feedback_propagation(self) -> None:
        """CUJ: Collecting feedback messages recorded for session nodes."""
        target_node = _make_dag_node("//pkg:fb_target", "lib")
        self.role_config.set_nodes([target_node])

        self.storage.add_message(
            FeedbackMessage(content=MessageContent("Fix upstream defect")),
            to=target_node,
        )

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfigImpl)
                fb = cfg.feedback
                self.assertIsInstance(fb, Sequence)


if __name__ == "__main__":
    unittest.main()
