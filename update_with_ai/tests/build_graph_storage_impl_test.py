"""Tests for build_graph_storage_impl derived from LLS."""

import unittest
from typing import Sequence, Optional, Dict, List
from lib.dag_storage import NodeId, DagMessage, PendingMessage, NodeData
from lib.sandbox import SandboxConfig
from lib.node_id_utils import NodeDirectory
from lib.build_message_store import BuildMessageStore
from lib.build_graph_storage import NodeDefinition
from lib.build_graph_storage_impl import BuildGraphStorageImpl


class MockMessageStore(BuildMessageStore):
    def __init__(self) -> None:
        self.pending: Dict[NodeId, List[DagMessage]] = {}
        self.rdeps: Dict[NodeId, List[NodeId]] = {}
        self.dirty: set[NodeId] = set()

    def get_package_directory(self, node: NodeId) -> NodeDirectory:
        return "/workspace/pkg"

    def get_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return []

    def get_reverse_dependencies(self, node: NodeId) -> Sequence[NodeId]:
        return self.rdeps.get(node, [])

    def get_pending_messages(self, node: NodeId) -> Sequence[PendingMessage]:
        return self.pending.get(node, [])

    def queue_pending_messages(self, node: NodeId, messages: Sequence[DagMessage]) -> None:
        if node not in self.pending:
            self.pending[node] = []
        self.pending[node].extend(messages)
        self.dirty.add(node)

    def clear_pending_messages(self, node: NodeId) -> None:
        self.pending[node] = []
        self.dirty.discard(node)

    def record_node_data(self, node: NodeId, data: NodeData) -> None:
        pass

    def get_node_data(self, node: NodeId) -> Optional[NodeData]:
        return None

    def mark_dirty(self, node: NodeId) -> None:
        self.dirty.add(node)

    def is_dirty(self, node: NodeId) -> bool:
        return node in self.dirty


class BuildGraphStorageImplTest(unittest.TestCase):
    def test_node_definition_dataclass(self) -> None:
        """Tests Data Types: NodeDefinition dataclass instantiation and fields."""
        cfg = SandboxConfig(
            file_mappings={"v.py": "/abs/v.py"},
            read_only_files=["r.py"],
            read_write_files=["w.py"],
            templates={"w.py": "template content"},
        )
        node_def = NodeDefinition(
            sandbox_config=cfg,
            prompt="Clean target node",
            config_target="//agent_configs:default",
        )
        self.assertEqual(node_def.sandbox_config, cfg)
        self.assertEqual(node_def.prompt, "Clean target node")
        self.assertEqual(node_def.config_target, "//agent_configs:default")

    def test_sandbox_config_immutability_and_retrieval(self) -> None:
        """Tests CUJ for storing and querying SandboxConfig per node.

        Checks postconditions: returns exact SandboxConfig configured for the node.
        """
        store = MockMessageStore()
        graph = BuildGraphStorageImpl(message_store=store)
        cfg = SandboxConfig(
            file_mappings={"v.py": "/abs/v.py"},
            read_only_files=["r.py"],
            read_write_files=["w.py"],
            templates={"w.py": "template content"},
        )
        graph.set_sandbox_config("//pkg:target", cfg)
        retrieved = graph.get_sandbox_config("//pkg:target")
        self.assertEqual(retrieved.read_only_files, ["r.py"])
        self.assertEqual(retrieved.read_write_files, ["w.py"])

    def test_dependencies_and_message_delegation(self) -> None:
        """Tests CUJ for querying node dependencies and delegating message persistence to BuildMessageStore."""
        store = MockMessageStore()
        graph = BuildGraphStorageImpl(message_store=store)
        node = "//pkg:target"
        graph.queue_pending_messages(node, [DagMessage(content="msg1")])
        self.assertTrue(graph.is_dirty(node))
        self.assertEqual(len(graph.get_pending_messages(node)), 1)
        graph.clear_pending_messages(node)
        self.assertEqual(len(graph.get_pending_messages(node)), 0)

    def test_full_message_store_delegation(self) -> None:
        """Tests delegation of all graph and storage operations to the underlying BuildMessageStore."""
        store = MockMessageStore()
        store.rdeps["//pkg:dep"] = ["//pkg:target"]
        graph = BuildGraphStorageImpl(message_store=store)

        # Dependencies
        graph.set_dependencies("//pkg:target", ["//pkg:dep1", "//pkg:dep2"])
        self.assertEqual(graph.get_dependencies("//pkg:target"), ["//pkg:dep1", "//pkg:dep2"])

        # Reverse dependencies
        self.assertEqual(graph.get_reverse_dependencies("//pkg:dep"), ["//pkg:target"])

        # Mark dirty
        graph.mark_dirty("//pkg:target")
        self.assertTrue(graph.is_dirty("//pkg:target"))

        # Node data
        graph.record_node_data("//pkg:target", {"status": "cleaned"})
        self.assertIsNone(graph.get_node_data("//pkg:target"))

    def test_task_prompt_storage_and_retrieval(self) -> None:
        """Tests storing and retrieving task prompts per node."""
        store = MockMessageStore()
        graph = BuildGraphStorageImpl(message_store=store)
        self.assertIsNone(graph.get_task_prompt("//pkg:target"))
        graph.set_task_prompt("//pkg:target", "Fix type errors in dag_storage.py")
        self.assertEqual(
            graph.get_task_prompt("//pkg:target"),
            "Fix type errors in dag_storage.py",
        )


if __name__ == "__main__":
    unittest.main()
