"""Unit tests for dag_cleaner_impl aligned with grounding specifications."""

import unittest
from typing import Dict, List, Set
from update_with_ai.parts.dag.lib.dag_cleaner import DagCleaner
from update_with_ai.parts.dag.lib.dag_cleaner_impl import (
    DagCleaner as DagCleanerImpl,
    __initialize__,
)
from update_with_ai.parts.dag.lib.dag_config import DagConfig
from update_with_ai.parts.dag.lib.dag_node_cleaner import NodeCleaner
from update_with_ai.parts.dag.lib.dag_storage import (
    DagStorage,
    Dependency,
    Message,
    Node,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase


class MockDagConfig:
    tier = "system"

    def __init__(self, node_visit_limit: int = 500) -> None:
        self.node_visit_limit = node_visit_limit


class MockDagStorage:
    tier = "system"

    def __init__(self) -> None:
        self.dependencies: Dict[Node, Set[Dependency]] = {}
        self.dependents: Dict[Node, Set[Node]] = {}
        self.messages: Dict[Node, Set[Message]] = {}
        self.dirty_nodes: Set[Node] = set()

    def get_dependencies(self, node: Node) -> Set[Dependency]:
        return set(self.dependencies.get(node, set()))

    def get_dependents(self, node: Node) -> Set[Node]:
        return set(self.dependents.get(node, set()))

    def get_messages(self, node: Node) -> Set[Message]:
        return set(self.messages.get(node, set()))

    def is_dirty(self, node: Node) -> bool:
        return node in self.dirty_nodes

    def register_dependent(self, node: Node) -> None:
        pass

    def clear_dependents(self, node: Node) -> None:
        pass

    def add_message(self, message: Message, to: Node) -> None:
        self.messages.setdefault(to, set()).add(message)
        self.dirty_nodes.add(to)

    def clear_messages(self, node: Node) -> None:
        self.messages[node] = set()
        self.dirty_nodes.discard(node)


class RecordingNodeCleaner:
    def __init__(self, storage: MockDagStorage, returns_continue: bool = True) -> None:
        self.storage = storage
        self.returns_continue = returns_continue
        self.cleaned_calls: List[Node] = []

    def clean(self, node: Node) -> bool:
        self.cleaned_calls.append(node)
        # Default behavior: cleaning resolves dirty state
        self.storage.dirty_nodes.discard(node)
        return self.returns_continue


class DagCleanerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = MockDagStorage()
        self.dag_cfg = MockDagConfig()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.registry.register_instance(self.storage, keys=[DagStorage], tier="system")
        self.registry.register_instance(self.dag_cfg, keys=[DagConfig], tier="system")

    def test_single_node_clean_success(self) -> None:
        """CUJ: Cleaning an isolated dirty root node."""
        root = Node(unit_address="//pkg:single")
        self.storage.dirty_nodes.add(root)
        cleaner = RecordingNodeCleaner(self.storage)

        with enter_phase("system", registry=self.registry) as scope:
            dag_cleaner = scope.get_singleton(DagCleaner)
            dag_cleaner.clean(root, cleaner)

            # Requirement: When cleaning a dirty node, the node cleaner is invoked to clean the node.
            self.assertEqual(cleaner.cleaned_calls, [root])
            # Requirement: Cleaning succeeds when all reachable nodes in the subgraph are clean.
            self.assertFalse(self.storage.is_dirty(root))

    def test_linear_pipeline_topological_order(self) -> None:
        """CUJ: Chain A depends on B, B depends on C executes in dependency-first order [C, B, A]."""
        a = Node(unit_address="//pkg:a")
        b = Node(unit_address="//pkg:b")
        c = Node(unit_address="//pkg:c")

        self.storage.dependencies[a] = {Dependency(node=b)}
        self.storage.dependencies[b] = {Dependency(node=c)}
        self.storage.dirty_nodes.update([a, b, c])

        cleaner = RecordingNodeCleaner(self.storage)

        with enter_phase("system", registry=self.registry) as scope:
            dag_cleaner = scope.get_singleton(DagCleaner)
            dag_cleaner.clean(a, cleaner)

            # Requirement: In each cleaning iteration, reachable nodes are visited in topological order.
            # Requirement: [DagCleaner] Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
            # Requirement: When cleaning a dirty node, the node cleaner is invoked to clean the node.
            # Requirement: [DagCleaner] When cleaning a dirty node using the node cleaner, cleaning delegates to the node cleaner.
            self.assertEqual(cleaner.cleaned_calls, [c, b, a])
            # Requirement: Cleaning succeeds when all reachable nodes in the subgraph are clean.
            # Requirement: [DagCleaner] Cleaning concludes when all nodes in the subgraph rooted at the node are clean.
            self.assertFalse(self.storage.is_dirty(a))
            self.assertFalse(self.storage.is_dirty(b))
            self.assertFalse(self.storage.is_dirty(c))

    def test_diamond_graph_topological_order(self) -> None:
        """CUJ: Diamond DAG: root -> (left, right) -> bottom executes bottom first, root last."""
        root = Node(unit_address="//pkg:root")
        left = Node(unit_address="//pkg:left")
        right = Node(unit_address="//pkg:right")
        bottom = Node(unit_address="//pkg:bottom")

        self.storage.dependencies[root] = {
            Dependency(node=left),
            Dependency(node=right),
        }
        self.storage.dependencies[left] = {Dependency(node=bottom)}
        self.storage.dependencies[right] = {Dependency(node=bottom)}
        self.storage.dirty_nodes.update([root, left, right, bottom])

        cleaner = RecordingNodeCleaner(self.storage)

        with enter_phase("system", registry=self.registry) as scope:
            dag_cleaner = scope.get_singleton(DagCleaner)
            dag_cleaner.clean(root, cleaner)

            # Requirement: Cleaning a target node collects all reachable dependencies from the node.
            # Requirement: In each cleaning iteration, reachable nodes are visited in topological order.
            self.assertEqual(cleaner.cleaned_calls[0], bottom)
            self.assertEqual(cleaner.cleaned_calls[-1], root)
            self.assertIn(cleaner.cleaned_calls[1], [left, right])
            self.assertIn(cleaner.cleaned_calls[2], [left, right])

    def test_only_dirty_nodes_are_cleaned(self) -> None:
        """CUJ: Clean nodes in reachable subgraph are not cleaned."""
        root = Node(unit_address="//pkg:root")
        dep1 = Node(unit_address="//pkg:dep1")
        dep2 = Node(unit_address="//pkg:dep2")

        self.storage.dependencies[root] = {Dependency(node=dep1), Dependency(node=dep2)}
        # Only dep2 and root are dirty
        self.storage.dirty_nodes.update([dep2, root])

        cleaner = RecordingNodeCleaner(self.storage)

        with enter_phase("system", registry=self.registry) as scope:
            dag_cleaner = scope.get_singleton(DagCleaner)
            dag_cleaner.clean(root, cleaner)

            # Requirement: Visiting a node checks whether the node is dirty, not whether it is cleaned.
            # Requirement: A node is cleaned only if it is dirty and all of its dependencies are clean.
            self.assertEqual(cleaner.cleaned_calls, [dep2, root])
            self.assertNotIn(dep1, cleaner.cleaned_calls)

    def test_halting_when_cleaner_returns_false(self) -> None:
        """CUJ: Halts execution immediately when cleaner returns False."""
        root = Node(unit_address="//pkg:root")
        dep = Node(unit_address="//pkg:dep")

        self.storage.dependencies[root] = {Dependency(node=dep)}
        self.storage.dirty_nodes.update([dep, root])

        # Cleaner halts on dep
        cleaner = RecordingNodeCleaner(self.storage, returns_continue=False)

        with enter_phase("system", registry=self.registry) as scope:
            dag_cleaner = scope.get_singleton(DagCleaner)
            dag_cleaner.clean(root, cleaner)

            # Requirement: If the node cleaner communicates that processing cannot continue, cleaning halts.
            # Requirement: [DagCleaner] If the node cleaner communicates that processing cannot continue, cleaning halts.
            self.assertEqual(cleaner.cleaned_calls, [dep])
            self.assertNotIn(root, cleaner.cleaned_calls)

    def test_node_visit_limit(self) -> None:
        """CUJ: Exceeding node visit limit halts with an unexpected failure."""
        self.dag_cfg.node_visit_limit = 2
        with enter_phase("system", registry=self.registry) as scope:
            dag_cleaner = scope.get_singleton(DagCleanerImpl)
            # Requirement: The node visit limit is obtained from the dag config.
            self.assertEqual(dag_cleaner.node_visit_limit, 2)

            root = Node(unit_address="//pkg:infinite")
            self.storage.dirty_nodes.add(root)

            class NonResolvingCleaner(NodeCleaner):
                def clean(self, node: Node) -> bool:
                    return True

            # Requirement: If visiting any node exceeds the node visit limit, the dag cleaner halts with an unexpected failure.
            with self.assertRaises(RuntimeError):
                dag_cleaner.clean(root, NonResolvingCleaner())


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
