"""Unit tests for bazel_graph_storage_impl aligned with grounding specifications."""

import os
import shutil
import tempfile
import unittest
from lib.bazel_graph_storage import BazelGraphStorage, NodeDefinition, TaskPrompt
from lib.bazel_graph_storage_impl import (
    BazelGraphStorage as BazelGraphStorageImpl,
    __initialize__,
)
from lib.bazel_node_id_utils import BazelNodeIdentifierUtility, NodeDirectory
from lib.dag_storage import Change, DagStorage, Dependency, Feedback, Node
from lib.lifecycle import LifecycleRegistry, enter_phase


class MockNodeIdUtils:
    tier = "system"

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir

    def normalize(self, raw_label: str) -> Node:
        return Node(address=raw_label)

    def extract_directory(self, node: Node) -> NodeDirectory:
        pkg = node.address.split(":")[0].lstrip("/")
        return NodeDirectory(path=os.path.join(self.base_dir, pkg))


class BazelGraphStorageImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.node_utils = MockNodeIdUtils(self.test_dir)
        self.registry.register_instance(
            self.node_utils, keys=[BazelNodeIdentifierUtility], tier="system"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_node_definition_and_dependencies(self) -> None:
        """CUJ: Storing and querying node definitions and direct graph dependencies."""
        node = Node(address="//pkg:target")
        dep_node = Node(address="//pkg:dep")
        defn = NodeDefinition(node=node, task_prompt=TaskPrompt("Clean prompt"))

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(BazelGraphStorage)
            self.assertIsInstance(storage, BazelGraphStorageImpl)
            assert isinstance(storage, BazelGraphStorageImpl)

            # Node definition
            storage._definitions[node] = defn
            # Requirement: The bazel graph storage provides task prompts and node definitions for declared nodes.
            # Requirement: The bazel graph storage maintains node definitions and task prompts mapped to nodes in dag storage.
            self.assertEqual(storage.get_node_definition(node), defn)

            # Dependencies
            dep = Dependency(node=dep_node, is_silent=False)
            storage._dependencies[node] = {dep}
            # Requirement: The bazel graph storage maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets.
            self.assertEqual(storage.get_dependencies(node), {dep})

    def test_messages_persistence_and_dirty_state(self) -> None:
        """CUJ: Adding messages serializes to package textproto and controls dirty state."""
        node = Node(address="//pkg/sub:target")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(BazelGraphStorage)
            # Requirement: The bazel graph storage creates missing package message files on write and treats absent files as empty.
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(storage.get_messages(node), set())

            # Add Change and Feedback messages
            # Requirement: Adding a message to a node records the message explaining why the node requires cleaning.
            # Requirement: The bazel graph storage serializes pending messages and reverse dependencies for nodes from dag storage into protobuf text format files using proto package store from update with ai proto ext.
            storage.add_message(Change(), to=node)
            storage.add_message(Feedback(), to=node)

            # Requirement: A node is dirty if it has messages explaining why it requires cleaning.
            self.assertTrue(storage.is_dirty(node))
            msgs = storage.get_messages(node)
            self.assertEqual(len(msgs), 2)
            self.assertTrue(any(isinstance(m, Change) for m in msgs))
            self.assertTrue(any(isinstance(m, Feedback) for m in msgs))

            # Verify textproto file was written to package directory
            # Requirement: All nodes located within the same package directory resolved by the bazel node identifier utility from bazel node id utils share a common package message file named `.update_with_ai.textproto`.
            # Requirement: The bazel graph storage reads and writes pending messages and reverse dependencies for nodes from dag storage in node directories resolved by the bazel node identifier utility from bazel node id utils.
            proto_path = os.path.join(self.test_dir, "pkg/sub", ".update_with_ai.textproto")
            self.assertTrue(os.path.isfile(proto_path))

            # Clear messages resets dirty state
            # Requirement: Clearing messages for a node removes all recorded messages explaining why it requires cleaning.
            storage.clear_messages(node)
            self.assertFalse(storage.is_dirty(node))
            self.assertEqual(storage.get_messages(node), set())

    def test_reverse_dependencies_registration_and_clearing(self) -> None:
        """CUJ: Registering dependent writes reverse dependency to non-silent dependencies."""
        upstream = Node(address="//pkg/lib:core")
        downstream = Node(address="//pkg/app:main")
        silent_upstream = Node(address="//pkg/silent:tool")

        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(BazelGraphStorage)
            assert isinstance(storage, BazelGraphStorageImpl)

            # Set dependencies: one normal, one silent
            storage._dependencies[downstream] = {
                Dependency(node=upstream, is_silent=False),
                Dependency(node=silent_upstream, is_silent=True),
            }

            # Register dependent
            # Requirement: Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
            # Requirement: Propagating dependencies exclude silent dependencies declared on a node.
            storage.register_dependent(downstream)

            # Non-silent upstream has downstream recorded as dependent
            self.assertIn(downstream, storage.get_dependents(upstream))
            # Silent upstream does NOT have downstream recorded
            self.assertNotIn(downstream, storage.get_dependents(silent_upstream))

            # Clear dependents on upstream
            # Requirement: Clearing the dependents of a node empties all recorded dependents for that node.
            storage.clear_dependents(upstream)
            self.assertEqual(storage.get_dependents(upstream), set())

    def test_failure_preserves_existing_records(self) -> None:
        """CUJ: Modifying records preserves existing records on disk when save fails."""
        node = Node(address="//pkg/fail:target")
        with enter_phase("system", registry=self.registry) as scope:
            storage = scope.get_singleton(BazelGraphStorage)
            # Requirement: The bazel graph storage creates missing package message files on write and treats absent files as empty.
            storage.add_message(Change(), to=node)
            self.assertEqual(len(storage.get_messages(node)), 1)

            proto_path = os.path.join(self.test_dir, "pkg/fail", ".update_with_ai.textproto")
            os.chmod(proto_path, 0o444)
            try:
                # Requirement: Modifying messages or reverse dependencies in the bazel graph storage preserves existing records on failure.
                storage.add_message(Feedback(), to=node)
                self.assertEqual(len(storage.get_messages(node)), 1)
            finally:
                os.chmod(proto_path, 0o666)

    def test_dag_storage_protocol_aliasing(self) -> None:
        """CUJ: Resolving singleton via DagStorage protocol alias."""
        with enter_phase("system", registry=self.registry) as scope:
            dag = scope.get_singleton(DagStorage)
            graph = scope.get_singleton(BazelGraphStorage)
            self.assertIs(dag, graph)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# - Declared dependencies marked propagating mark dependent nodes dirty when changed.
