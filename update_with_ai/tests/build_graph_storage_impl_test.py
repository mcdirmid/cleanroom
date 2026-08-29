"""
Tests for the BuildGraphStorage implementation.
"""

import os
import shutil
import tempfile
import unittest
from typing import Dict, List, Optional, Set, cast

from lib.build_graph_storage import (
    GraphConfig,
    NodeDefinition,
    NodeId,
    PackageDirectory,
)
from lib.build_graph_storage_impl import (
    BaseBuildGraphStorageImpl,
    BuildGraphStorageFileImpl,
)
from lib.build_message_store import BuildMessageStore, PackageMessageData
from lib.manifest_node_loader import ManifestNodeLoader, LoadedGraphManifests
from lib.dag_storage import (
    NodeMessage,
    MessageKind,
    PendingMessages,
    KnownReverseDependencies,
)
from lib.sandbox import SandboxConfig


def msg(text: str, kind: str = "change") -> NodeMessage:
    return NodeMessage(kind=cast(MessageKind, kind), text=text)


def _make_definition(prompt: str) -> NodeDefinition:
    return NodeDefinition(
        prompt=prompt,
        sandbox_config=SandboxConfig(
            file_mappings={},
            readable_paths=[],
            writable_paths=[],
            blame_targets={},
            search_result_limit=10,
        ),
    )


class _MockMessageStore(BuildMessageStore):
    """In-memory Mock replicating BuildMessageStore dataflow."""

    def __init__(self) -> None:
        self.pending: Dict[NodeId, List[NodeMessage]] = {}
        self.reverse_deps: Dict[NodeId, List[NodeId]] = {}
        self.calls: List[tuple] = []

    def read_package_messages(self, package_dir: PackageDirectory) -> PackageMessageData:
        self.calls.append(("read_package_messages", package_dir))
        return PackageMessageData(pending_messages=dict(self.pending), known_reverse_dependencies=dict(self.reverse_deps))

    def write_package_messages(self, package_dir: PackageDirectory, data: PackageMessageData) -> None:
        self.calls.append(("write_package_messages", package_dir, data))
        self.pending.update(data.pending_messages)
        self.reverse_deps.update(data.known_reverse_dependencies)

    def get_pending_messages(self, package_dir: PackageDirectory, node_id: NodeId) -> PendingMessages:
        self.calls.append(("get_pending_messages", package_dir, node_id))
        return list(self.pending.get(node_id, []))

    def add_pending_message(self, package_dir: PackageDirectory, node_id: NodeId, message: NodeMessage) -> None:
        self.calls.append(("add_pending_message", package_dir, node_id, message))
        self.pending.setdefault(node_id, []).append(message)

    def set_pending_messages(self, package_dir: PackageDirectory, node_id: NodeId, messages: PendingMessages) -> None:
        self.calls.append(("set_pending_messages", package_dir, node_id, messages))
        self.pending[node_id] = list(messages)

    def clear_pending_messages(self, package_dir: PackageDirectory, node_id: NodeId) -> None:
        self.calls.append(("clear_pending_messages", package_dir, node_id))
        self.pending.pop(node_id, None)

    def delete_node_messages(self, package_dir: PackageDirectory, node_id: NodeId) -> None:
        self.calls.append(("delete_node_messages", package_dir, node_id))
        self.pending.pop(node_id, None)
        self.reverse_deps.pop(node_id, None)

    def get_known_reverse_dependencies(self, package_dir: PackageDirectory, node_id: NodeId) -> KnownReverseDependencies:
        self.calls.append(("get_known_reverse_dependencies", package_dir, node_id))
        return list(self.reverse_deps.get(node_id, []))

    def add_known_reverse_dependency(self, package_dir: PackageDirectory, node_id: NodeId, reverse_dependency: NodeId) -> None:
        self.calls.append(("add_known_reverse_dependency", package_dir, node_id, reverse_dependency))
        rd_list = self.reverse_deps.setdefault(node_id, [])
        if reverse_dependency not in rd_list:
            rd_list.append(reverse_dependency)

    def clear_known_reverse_dependencies(self, package_dir: PackageDirectory, node_id: NodeId) -> None:
        self.calls.append(("clear_known_reverse_dependencies", package_dir, node_id))
        self.reverse_deps.pop(node_id, None)


class _MockManifestLoader(ManifestNodeLoader):
    """Mock replicating ManifestNodeLoader dataflow."""

    def __init__(self, manifests: Optional[LoadedGraphManifests] = None) -> None:
        self.manifests = manifests or LoadedGraphManifests(
            node_definitions={},
            node_dependencies={},
            package_directories={},
            propagating_dependencies={},
            silent_dependencies={},
        )
        self.calls: List[tuple] = []

    def resolve_graph(self, config: GraphConfig) -> LoadedGraphManifests:
        self.calls.append(("resolve_graph", config))
        return self.manifests


class _MockGraphStorageImpl(BaseBuildGraphStorageImpl):
    def __init__(
        self,
        adjacency: Dict[NodeId, List[NodeId]],
        definitions: Optional[Dict[NodeId, NodeDefinition]] = None,
        package_dirs: Optional[Dict[NodeId, PackageDirectory]] = None,
        propagating: Optional[Dict[NodeId, List[NodeId]]] = None,
        message_store: Optional[BuildMessageStore] = None,
    ) -> None:
        self._adjacency = adjacency
        self._definitions = definitions or {}
        self._package_dirs = package_dirs or {}
        self._propagating = propagating if propagating is not None else adjacency
        super().__init__(
            GraphConfig(graph_source="mock-graph-source"),
            message_store=message_store or _MockMessageStore(),
            manifest_loader=_MockManifestLoader(),
        )

    def _build_adjacency(self) -> Dict[NodeId, List[NodeId]]:
        return self._adjacency

    def _build_propagating_deps(self) -> Dict[NodeId, List[NodeId]]:
        return self._propagating

    def _build_definitions(self) -> Dict[NodeId, NodeDefinition]:
        return self._definitions

    def _build_package_dirs(self) -> Dict[NodeId, PackageDirectory]:
        return self._package_dirs


def _make_pkg_dir(root: str, name: str) -> str:
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    return d


class TestBaseBuildGraphStorageImplConfig(unittest.TestCase):
    def test_config_without_graph_source_or_workspace_root_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            BaseBuildGraphStorageImpl(GraphConfig(), message_store=_MockMessageStore(), manifest_loader=_MockManifestLoader())
        self.assertIn("graph_source", str(ctx.exception))


class TestBaseBuildGraphStorageImplResolution(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_root = tempfile.mkdtemp(prefix="bgsi_resolve_")
        self.pkg_a = _make_pkg_dir(self._tmp_root, "pkg_a")
        self.pkg_b = _make_pkg_dir(self._tmp_root, "pkg_b")
        self.pkg_c = _make_pkg_dir(self._tmp_root, "pkg_c")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_root, ignore_errors=True)

    def _graph(self) -> BaseBuildGraphStorageImpl:
        return _MockGraphStorageImpl(
            adjacency={
                "//pkg:a": ["//pkg:b", "//pkg:c"],
                "//pkg:b": [],
                "//pkg:c": [],
            },
            definitions={"//pkg:a": _make_definition("prompt-a")},
            package_dirs={
                "//pkg:a": self.pkg_a,
                "//pkg:b": self.pkg_b,
                "//pkg:c": self.pkg_c,
            },
        )

    def test_resolve_node_definition_returns_prompt_and_sandbox_config(self) -> None:
        graph = self._graph()
        definition = graph.resolve_node_definition("//pkg:a")
        self.assertEqual(definition.prompt, "prompt-a")
        self.assertIsInstance(definition.sandbox_config, SandboxConfig)

    def test_resolve_package_directory_returns_directory(self) -> None:
        graph = self._graph()
        self.assertEqual(graph.resolve_package_directory("//pkg:a"), self.pkg_a)

    def test_get_node_dependencies_returns_dependencies(self) -> None:
        graph = self._graph()
        self.assertEqual(
            graph.get_node_dependencies("//pkg:a"), ["//pkg:b", "//pkg:c"]
        )

    def test_get_propagating_dependencies_returns_propagating_subset(self) -> None:
        graph = _MockGraphStorageImpl(
            adjacency={"//pkg:a": ["//pkg:b", "//pkg:c"]},
            propagating={"//pkg:a": ["//pkg:b"]},
            package_dirs={"//pkg:a": self.pkg_a, "//pkg:b": self.pkg_b},
        )
        self.assertEqual(graph.get_propagating_dependencies("//pkg:a"), ["//pkg:b"])


class TestBaseBuildGraphStorageImplSubgraphs(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_root = tempfile.mkdtemp(prefix="bgsi_subgraph_")
        self.pkg_a = _make_pkg_dir(self._tmp_root, "pkg_a")
        self.pkg_b = _make_pkg_dir(self._tmp_root, "pkg_b")
        self.pkg_c = _make_pkg_dir(self._tmp_root, "pkg_c")
        self.pkg_d = _make_pkg_dir(self._tmp_root, "pkg_d")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_root, ignore_errors=True)

    def test_get_subgraph_closure_order_is_topological(self) -> None:
        graph = _MockGraphStorageImpl(
            adjacency={
                "//pkg:a": ["//pkg:b", "//pkg:c"],
                "//pkg:b": ["//pkg:d"],
                "//pkg:c": ["//pkg:d"],
                "//pkg:d": [],
            },
            package_dirs={
                "//pkg:a": self.pkg_a,
                "//pkg:b": self.pkg_b,
                "//pkg:c": self.pkg_c,
                "//pkg:d": self.pkg_d,
            },
        )
        subgraph = graph.get_subgraph("//pkg:a")
        self.assertEqual(set(subgraph), {"//pkg:a", "//pkg:b", "//pkg:c", "//pkg:d"})
        self.assertLess(subgraph.index("//pkg:d"), subgraph.index("//pkg:b"))
        self.assertLess(subgraph.index("//pkg:d"), subgraph.index("//pkg:c"))
        self.assertLess(subgraph.index("//pkg:b"), subgraph.index("//pkg:a"))
        self.assertLess(subgraph.index("//pkg:c"), subgraph.index("//pkg:a"))

    def test_get_subgraph_isolated_node_returns_single_node(self) -> None:
        graph = _MockGraphStorageImpl(
            adjacency={"//pkg:a": []},
            package_dirs={"//pkg:a": self.pkg_a},
        )
        self.assertEqual(graph.get_subgraph("//pkg:a"), ["//pkg:a"])


class TestDynamicReverseDependencyRecording(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_root = tempfile.mkdtemp(prefix="bgsi_rdep_")
        self.pkg_a = _make_pkg_dir(self._tmp_root, "pkg_a")
        self.pkg_b = _make_pkg_dir(self._tmp_root, "pkg_b")
        self.pkg_c = _make_pkg_dir(self._tmp_root, "pkg_c")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_root, ignore_errors=True)

    def test_get_node_dependencies_records_known_reverse_dependency(self) -> None:
        graph = _MockGraphStorageImpl(
            adjacency={
                "//pkg:a": ["//pkg:b"],
                "//pkg:b": [],
                "//pkg:c": [],
            },
            definitions={},
            package_dirs={
                "//pkg:a": self.pkg_a,
                "//pkg:b": self.pkg_b,
                "//pkg:c": self.pkg_c,
            },
        )
        graph.get_node_dependencies("//pkg:a")

        self.assertEqual(
            graph.get_known_reverse_dependencies("//pkg:b"), ["//pkg:a"]
        )
        self.assertEqual(graph.get_known_reverse_dependencies("//pkg:c"), [])


class TestMessageOperationsDelegation(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.pkg_dir = _make_pkg_dir(self.temp_dir, "pkg")
        self.graph = _MockGraphStorageImpl(
            adjacency={"//pkg:target": []},
            package_dirs={"//pkg:target": self.pkg_dir},
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_get_clear_messages(self) -> None:
        target = "//pkg:target"
        self.graph.add_messages(target, [msg("hello", "change")])
        self.assertEqual(len(self.graph.get_pending_messages(target)), 1)

        self.graph.clear_pending_messages(target)
        self.assertEqual(self.graph.get_pending_messages(target), [])

    def test_delete_node_data(self) -> None:
        target = "//pkg:target"
        self.graph.add_messages(target, [msg("hello", "change")])
        self.graph.delete_node_data(target)
        self.assertEqual(self.graph.get_pending_messages(target), [])


if __name__ == "__main__":
    unittest.main()
