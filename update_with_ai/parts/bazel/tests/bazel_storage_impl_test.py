"""Unit tests for bazel_storage_impl aligned with grounding specifications."""

import os
import shutil
import tempfile
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
from update_with_ai.parts.bazel.lib.file_paths import (
    AbsolutePath,
    DirectoryPath,
    FilePaths,
    HostPath,
    WorkspacePath,
    WorkspaceRoot,
)
from update_with_ai.parts.bazel.lib.bazel_target import BazelTarget, NodeDirectory
from update_with_ai.parts.dag.lib.dag_storage import (
    Change,
    DagStorage,
    Dependency,
    Feedback,
    Node,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase


def _make_node_dir(path: str) -> NodeDirectory:
    obj = object.__new__(NodeDirectory)
    object.__setattr__(obj, "path", path)
    return obj


class MockNodeIdUtils:
    tier = "system"

    def normalize(self, raw_label: str, role_label: str = "") -> Node:
        if "#" in raw_label:
            u, r = raw_label.split("#", 1)
            return Node(unit_address=u, role_address=r)
        return Node(unit_address=raw_label, role_address=role_label)

    def extract_directory(self, node: Node) -> NodeDirectory:
        pkg = node.unit_address.split(":")[0].lstrip("/")
        return _make_node_dir(pkg)


class MockFilePaths:
    tier = "system"

    def __init__(self, root_dir: str) -> None:
        self.root_dir = root_dir

    def get_workspace_root(self) -> WorkspaceRoot:
        obj = object.__new__(WorkspaceRoot)
        object.__setattr__(obj, "path", self.root_dir)
        return obj

    def resolve_directory(
        self, root: WorkspaceRoot, relative: WorkspacePath
    ) -> DirectoryPath:
        obj = object.__new__(DirectoryPath)
        joined = os.path.join(root.path, relative.path) if relative.path else root.path
        object.__setattr__(obj, "path", joined)
        return obj

    def create_host_path(self, path: str) -> HostPath:
        obj = object.__new__(HostPath)
        object.__setattr__(obj, "path", path)
        return obj

    def create_absolute_path(self, path: str) -> AbsolutePath:
        obj = object.__new__(AbsolutePath)
        object.__setattr__(obj, "path", path)
        return obj

    def create_workspace_path(self, path: str) -> WorkspacePath:
        obj = object.__new__(WorkspacePath)
        object.__setattr__(obj, "path", path)
        return obj

    def create_directory_path(self, path: str) -> DirectoryPath:
        obj = object.__new__(DirectoryPath)
        object.__setattr__(obj, "path", path)
        return obj

    def resolve_path(
        self, root: WorkspaceRoot, relative: WorkspacePath
    ) -> AbsolutePath:
        obj = object.__new__(AbsolutePath)
        joined = os.path.join(root.path, relative.path)
        object.__setattr__(obj, "path", joined)
        return obj


class BazelStorageImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.orig_env = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.test_dir
        self.registry = LifecycleRegistry()
        self.file_paths_service = MockFilePaths(self.test_dir)
        self.registry.register_instance(
            self.file_paths_service, keys=[FilePaths], tier="system"
        )
        __initialize__(self.registry)
        self.node_utils = MockNodeIdUtils()
        self.registry.register_instance(
            self.node_utils, keys=[BazelTarget], tier="system"
        )

    def tearDown(self) -> None:
        if self.orig_env is not None:
            os.environ["BUILD_WORKSPACE_DIRECTORY"] = self.orig_env
        else:
            os.environ.pop("BUILD_WORKSPACE_DIRECTORY", None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_node_definition_and_dependencies(self) -> None:
        """CUJ: Storing and querying node definitions and direct graph dependencies."""
        node = Node(unit_address="//pkg:target", role_address="")
        dep_node = Node(unit_address="//pkg:dep", role_address="")
        defn = NodeDefinition(node=node, task_prompt=TaskPrompt("Clean prompt"))

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            self.assertIsInstance(storage, AgentStorageImpl)
            assert isinstance(storage, AgentStorageImpl)

            # Node definition
            storage._definitions[node] = defn
            # Requirement: [AgentStorage] The agent storage provides task prompts and node definitions for declared nodes.
            # Requirement: The agent storage maintains node definitions and task prompts mapped to nodes in dag storage.
            self.assertEqual(storage.get_node_definition(node), defn)

            # Dependencies
            dep = Dependency(node=dep_node, is_silent=False)
            storage._dependencies[node] = {dep}
            # Requirement: [AgentStorage] The agent storage maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets.
            self.assertEqual(storage.get_dependencies(node), {dep})

    def test_messages_persistence_and_dirty_state(self) -> None:
        """CUJ: Adding messages serializes to package textproto and controls dirty state."""
        node = Node(unit_address="//pkg/sub:target", role_address="")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            # Requirement: The agent storage resolves the package directory against the workspace root to read and write message files at their absolute path, creating files if missing and ignoring absent files on read.
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(storage.get_messages(node), set())

            # Add Change and Feedback messages
            # Requirement: Adding a message to a node records the message explaining why the node requires cleaning.
            # Requirement: [DagStorage] Adding a message to a node records the message for that node.
            # Requirement: The agent storage serializes pending messages and reverse dependencies for nodes from dag storage into protobuf text format files using proto package store from update with ai proto ext.
            storage.add_message(Change(), to=node)
            storage.add_message(Feedback(), to=node)

            # Requirement: A node in dag storage is dirty if it has messages explaining why it requires cleaning, or if its declared source file is missing from the workspace root, recording a change message to implement the source file for the node.
            # Requirement: [DagStorage] A node is dirty if, but not only if, it has messages.
            self.assertTrue(storage.is_dirty(node))
            msgs = storage.get_messages(node)
            self.assertEqual(len(msgs), 2)
            self.assertTrue(any(isinstance(m, Change) for m in msgs))
            self.assertTrue(any(isinstance(m, Feedback) for m in msgs))

            # Verify textproto file was written to package directory
            # Requirement: All nodes located within the same package directory resolved by the bazel target share a common package message file named `.update_with_ai.textproto`.
            proto_path = os.path.join(
                self.test_dir, "pkg/sub", ".update_with_ai.textproto"
            )
            self.assertTrue(os.path.isfile(proto_path))

            # Clear messages resets dirty state
            # Requirement: Clearing messages for a node removes all recorded messages explaining why it requires cleaning.
            # Requirement: [DagStorage] Clearing messages for a node removes all recorded messages for that node.
            storage.clear_messages(node)
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(storage.get_messages(node), set())

    def test_missing_source_file_dirty_state(self) -> None:
        """CUJ: A node is dirty when its declared source file is missing from the workspace root."""
        node = Node(unit_address="//pkg/src:target", role_address="")
        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            # Node with declared source file that does not exist yet
            rel_path = "pkg/src/target.py"
            storage._source_files[node] = rel_path
            # Requirement: A node in dag storage is dirty if it has messages explaining why it requires cleaning, or if its declared source file is missing from the workspace root, recording a change message to implement the source file for the node.
            # Requirement: [DagStorage] A node is dirty if, but not only if, it has messages.
            self.assertTrue(storage.is_dirty(node))

            # Calling is_dirty recorded a change message to implement the source file
            msgs = storage.get_messages(node)
            self.assertEqual(len(msgs), 1)
            msg = next(iter(msgs))
            self.assertIsInstance(msg, Change)
            self.assertEqual(msg.content, f"implement {rel_path}")

            # Even after creating the declared source file on disk, the node remains dirty because the recorded change message persists
            abs_src = os.path.join(self.test_dir, rel_path)
            os.makedirs(os.path.dirname(abs_src), exist_ok=True)
            with open(abs_src, "w", encoding="utf-8") as f:
                f.write("# source file\n")
            self.assertTrue(storage.is_dirty(node))

            # Clearing messages once the source file exists clears the dirty state
            # Requirement: Clearing messages for a node removes all recorded messages explaining why it requires cleaning.
            # Requirement: [DagStorage] Clearing messages for a node removes all recorded messages for that node.
            storage.clear_messages(node)
            self.assertFalse(storage.is_dirty(node))

    def test_reverse_dependencies_registration_and_clearing(self) -> None:
        """CUJ: Registering dependent writes reverse dependency to non-silent dependencies."""
        upstream = Node(unit_address="//pkg/lib:core", role_address="")
        downstream = Node(unit_address="//pkg/app:main", role_address="")
        silent_upstream = Node(unit_address="//pkg/silent:tool", role_address="")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)

            # Set dependencies: one normal, one silent
            storage._dependencies[downstream] = {
                Dependency(node=upstream, is_silent=False),
                Dependency(node=silent_upstream, is_silent=True),
            }

            # Register dependent
            # Requirement: Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
            # Requirement: [DagStorage] Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
            # Requirement: Propagating dependencies exclude silent dependencies declared on a node.
            storage.register_dependent(downstream)

            # Non-silent upstream has downstream recorded as dependent
            self.assertIn(downstream, storage.get_dependents(upstream))
            # Silent upstream does NOT have downstream recorded
            self.assertNotIn(downstream, storage.get_dependents(silent_upstream))

            # Clear dependents on upstream
            # Requirement: Clearing the dependents of a node empties all recorded dependents for that node.
            # Requirement: [DagStorage] Clearing the dependents of a node empties all recorded dependents for that node.
            storage.clear_dependents(upstream)
            self.assertEqual(storage.get_dependents(upstream), set())

    def test_dag_storage_protocol_aliasing(self) -> None:
        """CUJ: Resolving singleton via DagStorage protocol alias."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DagStorage)
            graph = scope.get_singleton(AgentStorage)
            self.assertIs(dag, graph)

    def test_save_package_data_os_error_handled(self) -> None:
        """CUJ: Handling filesystem write errors during package data persistence."""
        node = Node(unit_address="//pkg/err:target", role_address="")
        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(AgentStorage)
            assert isinstance(storage, AgentStorageImpl)
            with patch(
                "update_with_ai.parts.bazel.lib.bazel_storage_impl.Path.write_text",
                side_effect=OSError("Disk write failed"),
            ):
                # Requirement: The agent storage resolves the package directory against the workspace root to read and write message files at their absolute path, creating files if missing and ignoring absent files on read.
                # Requirement: [DagStorage] Adding a message to a node records the message for that node.
                storage.add_message(Change(), to=node)
                self.assertEqual(storage.get_messages(node), set())


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - [AgentStorage] Declared dependencies marked propagating mark dependent nodes dirty when changed.
