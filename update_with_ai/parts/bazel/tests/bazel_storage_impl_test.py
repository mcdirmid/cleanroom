"""Unit tests for bazel_storage_impl aligned with grounding specifications."""

import os
import shutil
import tempfile
from typing import Any, cast
import unittest
from unittest.mock import patch
from update_with_ai.parts.agent.lib.agent_storage import (
    AgentStorage,
    NodeDefinition,
    TaskPrompt,
)
from update_with_ai.parts.bazel.lib.bazel_storage_impl import (
    AgentStorage as AgentStorageImpl,
    __initialize__,
)
from update_with_ai.parts.core.lib.file_paths import (
    AbsolutePath,
    FilePathManager,
    HostPath,
    PathString,
    WorkspacePath,
    WorkspaceRoot,
)
from update_with_ai.parts.bazel.lib.bazel_target import BazelTarget, NodeDirectory
from update_with_ai.parts.dag.lib.dag_storage import (
    ChangeMessage,
    DagStorage,
    DagDependency,
    FeedbackMessage,
    DagNode,
    RoleAddress,
    UnitAddress,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase


def _make_dag_node(unit_address: str, role_address: str = "") -> DagNode:
    return DagNode(unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address))


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


class FakeFilePaths:
    tier = "system"

    def __init__(self, root_dir: str) -> None:
        self.root_dir = root_dir

    def get_workspace_root(self) -> WorkspaceRoot:
        return WorkspaceRoot(path=PathString(self.root_dir))

    def create_host_path(self, path: str) -> HostPath:
        return HostPath(path=PathString(path))

    def create_absolute_path(self, path: str) -> AbsolutePath:
        return AbsolutePath(path=PathString(path))

    def create_workspace_path(self, path: str) -> WorkspacePath:
        return WorkspacePath(path=PathString(path))

    def resolve_path(
        self, root: AbsolutePath, relative: WorkspacePath
    ) -> AbsolutePath:
        joined = os.path.join(root.path, relative.path)
        return AbsolutePath(path=PathString(joined))


class BazelStorageImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.orig_env = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.test_dir
        self.registry = LifecycleRegistry()
        self.file_paths_service = FakeFilePaths(self.test_dir)
        self.node_id_utils = FakeBazelTarget()

        self.registry.register_instance(
            self.file_paths_service, keys=[FilePathManager], tier="system"
        )
        self.registry.register_instance(
            self.node_id_utils, keys=[BazelTarget], tier="system"
        )
        __initialize__(self.registry)

    def tearDown(self) -> None:
        if self.orig_env is not None:
            os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.orig_env
        else:
            os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_node_definition_and_dependencies(self) -> None:
        """CUJ: Storing and querying node definitions and direct graph dependencies."""
        node = _make_dag_node("//pkg:target")
        dep_node = _make_dag_node("//pkg:dep")
        defn = NodeDefinition(task_prompt=TaskPrompt("Clean prompt"))

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            self.assertIsInstance(storage, AgentStorageImpl)
            assert isinstance(storage, AgentStorageImpl)

            # Store node definition
            storage.store_node_definition(node, defn)
            # Requirement: [AgentStorage] MUST provide node definitions for declared nodes.
            # Requirement: MUST provide node definitions for declared nodes.
            self.assertEqual(storage.get_node_definition(node), defn)
            # Requirement: MUST provide task prompts for declared nodes.
            self.assertEqual(storage.get_task_prompt(node), defn.task_prompt)

            # Dependencies
            dep = DagDependency(node=dep_node, is_silent=False)
            cast(Any, storage)._dependencies[node] = {dep}
            # Requirement: [AgentStorage] MUST return the set of upstream dependencies for the node.
            # Requirement: MUST return the set of upstream dependencies for the node.
            self.assertEqual(storage.get_dependencies(node), {dep})

    def test_messages_persistence_and_dirty_state(self) -> None:
        """CUJ: Adding messages serializes to package textproto and controls dirty state."""
        node = _make_dag_node("//pkg/sub:target")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(storage.get_messages(node), set())

            # Add ChangeMessage and FeedbackMessage messages
            # Requirement: MUST serialize pending messages into package .update_with_ai.textproto files.
            # Requirement: MUST add the message to the node.
            storage.add_message(ChangeMessage(), to=node)
            storage.add_message(FeedbackMessage(), to=node)

            # Requirement: WHEN a node has messages or its declared source file is missing from the workspace root, MUST return true.
            # Requirement: WHEN the node has messages, MUST return true.
            self.assertTrue(storage.is_dirty(node))
            msgs = storage.get_messages(node)
            self.assertEqual(len(msgs), 2)
            self.assertTrue(any(isinstance(m, ChangeMessage) for m in msgs))
            self.assertTrue(any(isinstance(m, FeedbackMessage) for m in msgs))

            # Verify textproto file was written to package directory
            proto_path = os.path.join(
                self.test_dir, "pkg/sub", ".update_with_ai.textproto"
            )
            self.assertTrue(os.path.isfile(proto_path))

            # Clear messages resets dirty state
            # Requirement: MUST clear all messages from the node.
            storage.clear_messages(node)
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(storage.get_messages(node), set())

    def test_missing_source_file_dirty_state(self) -> None:
        """CUJ: A node is dirty when its declared source file is missing from the workspace root."""
        node = _make_dag_node("//pkg/src:target", "lib")
        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            # DagNode with declared source file that does not exist yet
            rel_path = "pkg/src/target.py"
            cast(Any, storage)._source_files[node] = rel_path
            # Requirement: WHEN a declared source file is missing from the workspace root, MUST record a change message to implement the source file.
            # Requirement: WHEN a node has messages or its declared source file is missing from the workspace root, MUST return true.
            self.assertTrue(storage.is_dirty(node))

            # Calling is_dirty recorded a change message to implement the source file
            msgs = storage.get_messages(node)
            self.assertEqual(len(msgs), 1)
            msg = next(iter(msgs))
            assert isinstance(msg, ChangeMessage)
            self.assertEqual(msg.content, f"implement {rel_path}")

            # Consecutive call to is_dirty is idempotent and does not add duplicate messages
            self.assertTrue(storage.is_dirty(node))
            self.assertEqual(len(storage.get_messages(node)), 1)

            # Even after creating the declared source file on disk, the node remains dirty because the recorded change message persists
            abs_src = os.path.join(self.test_dir, rel_path)
            os.makedirs(os.path.dirname(abs_src), exist_ok=True)
            with open(abs_src, "w", encoding="utf-8") as f:
                f.write("# source file\n")
            self.assertTrue(storage.is_dirty(node))

            # Clearing messages once the source file exists clears the dirty state
            # Requirement: MUST clear all messages from the node.
            storage.clear_messages(node)
            self.assertFalse(storage.is_dirty(node))

    def test_reverse_dependencies_registration_and_clearing(self) -> None:
        """CUJ: Registering dependent writes reverse dependency to non-silent dependencies."""
        upstream = _make_dag_node("//pkg/lib:core")
        downstream = _make_dag_node("//pkg/app:main")
        silent_upstream = _make_dag_node("//pkg/silent:tool")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            # Set dependencies: one normal, one silent
            cast(Any, storage)._dependencies[downstream] = {
                DagDependency(node=upstream, is_silent=False),
                DagDependency(node=silent_upstream, is_silent=True),
            }

            # Register dependent
            # Requirement: MUST serialize reverse dependencies into package .update_with_ai.textproto files.
            # Requirement: MUST exclude silent dependencies when serializing reverse dependencies.
            # Requirement: MUST register the node as a dependent across its non-silent dependencies.
            storage.register_dependent(downstream)

            # Non-silent upstream has downstream recorded as dependent
            self.assertIn(downstream, storage.get_dependents(upstream))
            # Silent upstream does NOT have downstream recorded
            self.assertNotIn(downstream, storage.get_dependents(silent_upstream))

            # Clear dependents on upstream
            # Requirement: MUST clear all registered dependents from the node.
            storage.clear_dependents(upstream)
            self.assertEqual(storage.get_dependents(upstream), set())

    def test_dag_storage_protocol_aliasing(self) -> None:
        """CUJ: Resolving singleton via DagStorage protocol alias."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DagStorage)
            graph = scope.get_singleton(AgentStorage)
            self.assertIs(dag, graph)


    def test_mark_dependents_dirty(self) -> None:
        """CUJ: Propagating dirty state delivers a ChangeMessage to registered downstream dependents."""
        upstream = _make_dag_node("//pkg/lib:core")
        downstream = _make_dag_node("//pkg/app:main")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            # Register downstream as dependent of upstream
            cast(Any, storage)._dependencies[downstream] = {
                DagDependency(node=upstream, is_silent=False),
            }
            storage.register_dependent(downstream)
            self.assertIn(downstream, storage.get_dependents(upstream))

            # Mark dependents dirty
            # Requirement: MUST mark dependent nodes dirty when propagating dependencies change.
            storage.mark_dependents_dirty(upstream)

            # Downstream receives a ChangeMessage and becomes dirty
            self.assertTrue(storage.is_dirty(downstream))
            msgs = storage.get_messages(downstream)
            self.assertEqual(len(msgs), 1)
            self.assertTrue(any(isinstance(m, ChangeMessage) for m in msgs))


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
