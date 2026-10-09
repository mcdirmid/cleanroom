# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-07T23:58:18Z
# LAST_CHANGED: 2026-10-07T00:00:00Z
# CHANGE: new file
# CODE_HASH: 611ced6177e2
# COVERAGE_AUDIT: 2026-10-07T23:58:18Z
# QA_AUDIT: 2026-10-07T23:58:18Z
# --- END CLEANROOM METADATA ---

"""Unit tests for uv_node_config_impl aligned with low-level specifications."""

import os
import tempfile
import unittest
from typing import Any, Dict, Optional, Sequence, Set, cast

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
    RoleConfig,
    StepSection,
    VerificationCheck,
)
from update_with_ai.parts.agent.lib.agent_storage import AgentStorage
from update_with_ai.parts.uv.lib.uv_manifest_loader import (
    UvManifestLoader,
    TargetManifest,
    TargetLabel,
    VerificationCommand,
)
from update_with_ai.parts.uv.lib.uv_node_config_impl import (
    AliasManager as AliasManagerImpl,
    NodeConfig as NodeConfigImpl,
    __initialize__,
)
from update_with_ai.parts.uv.lib.uv_target import UvTarget, NodeDirectory, TargetIdentifier
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
        return NodeDirectory(PathString(raw_pkg))


class TestUvNodeConfigImpl(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        self.file_paths = FakeFilePaths("/workspace")
        self.uv_target = FakeUvTarget()
        self.role_config = FakeRoleConfig()
        self.agent_config = FakeAgentConfig(is_step_mode=True)
        self.storage = FakeAgentStorage()
        self.manifest_loader = FakeManifestLoader()

        self.registry.register_instance(
            self.file_paths, keys=[FilePathManager], tier="system"
        )
        self.registry.register_instance(
            self.uv_target, keys=[UvTarget], tier="system"
        )
        self.registry.register_instance(
            self.agent_config, keys=[AgentConfig], tier="system"
        )
        self.registry.register_instance(
            self.storage, keys=[AgentStorage, DagStorage], tier="system"
        )
        self.registry.register_instance(
            self.manifest_loader, keys=[UvManifestLoader], tier="system"
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

                # Unbound file
                unbound = mgr.convert("unknown/file.txt")
                self.assertIsInstance(unbound, FileAlias)
                self.assertIsInstance(unbound, UnboundFile)

                # Bound file
                bound = mgr.convert("pkg/target.py")
                self.assertIsInstance(bound, FileAlias)
                self.assertIsInstance(bound, BoundFile)
                assert isinstance(bound, BoundFile)
                self.assertEqual(bound.relative_path, "pkg/target.py")

                # Basename match
                short_bound = mgr.convert("target.py")
                self.assertEqual(short_bound, bound)

    def test_node_config_file_sets(self) -> None:
        """CUJ: NodeConfig aggregates read-write and read-only files across active nodes."""
        node = _make_dag_node("//pkg:target", "lib")
        dep_node = _make_dag_node("//pkg:dep", "lib")
        manifest = TargetManifest(
            label=cast(Any, "//pkg:target"),
            source_file=cast(Any, RelativePath("pkg/target.py")),
            silent_source_files=[cast(Any, RelativePath("pkg/silent.py"))],
            dependencies=[cast(Any, "//pkg:dep")],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
        )
        dep_manifest = TargetManifest(
            label=cast(Any, "//pkg:dep"),
            source_file=cast(Any, RelativePath("pkg/dep.py")),
            silent_source_files=[],
            dependencies=[],
            silent_dependencies=[],
            star_dependencies=[],
            feedback_dependencies=[],
        )
        self.manifest_loader.manifests["//pkg:target"] = manifest
        self.manifest_loader.manifests["//pkg:dep"] = dep_manifest

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfig)
                self.assertIsInstance(cfg, NodeConfigImpl)

                rw_paths = {f.relative_path for f in cfg.read_write_files}
                self.assertIn("pkg/target.py", rw_paths)
                self.assertIn("pkg/silent.py", rw_paths)

                ro_paths = {f.relative_path for f in cfg.read_only_files}
                self.assertIn("pkg/dep.py", ro_paths)

    def test_step_mode_and_guide(self) -> None:
        """CUJ: Step mode and guide file resolution when active."""
        manifest = TargetManifest(
            label=cast(Any, "//pkg:target"),
            source_file=cast(Any, RelativePath("pkg/target.py")),
            guide_target=cast(Any, "//guides:my_guide"),
            allows_step_mode=True,
        )
        self.manifest_loader.manifests["//pkg:target"] = manifest

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfig)
                self.assertTrue(cfg.allows_step_mode)
                self.assertTrue(cfg.is_step_mode)
                self.assertIsNotNone(cfg.guide_file)
                assert cfg.guide_file is not None
                self.assertEqual(cfg.guide_file.relative_path, "my_guide.md")

    def test_blame_targets_mapping(self) -> None:
        """CUJ: Feedback dependencies map into blame targets."""
        node = _make_dag_node("//pkg:target", "lib")
        dep_node = _make_dag_node("//pkg:contract", "low")
        manifest = TargetManifest(
            label=cast(Any, "//pkg:target"),
            source_file=cast(Any, RelativePath("pkg/target.py")),
            dependencies=[cast(Any, "//pkg:contract")],
            feedback_dependencies=[cast(Any, "//pkg:contract")],
        )
        dep_manifest = TargetManifest(
            label=cast(Any, "//pkg:contract"),
            source_file=cast(Any, RelativePath("pkg/contract.pyi")),
        )
        self.manifest_loader.manifests["//pkg:target"] = manifest
        self.manifest_loader.manifests["//pkg:contract"] = dep_manifest

        with enter_phase("system", registry=self.registry):
            with enter_phase("agent_session", registry=self.registry) as scope:
                cfg = scope.get_singleton(NodeConfig)
                blame = cfg.blame_targets_by_node
                self.assertIn(node, blame)
                rel_paths = {b.relative_path for b in blame[node]}
                self.assertIn("pkg/contract.pyi", rel_paths)


if __name__ == "__main__":
    unittest.main()
