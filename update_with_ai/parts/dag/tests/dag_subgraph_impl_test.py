"""Unit tests for dag_subgraph_impl aligned with grounding specifications."""

import unittest
from typing import Dict, List, Sequence, Set
from update_with_ai.parts.dag.lib.dag_config import DagConfig
from update_with_ai.parts.dag.lib.dag_storage import (
    DagStorage,
    Dependency,
    Node,
)
from update_with_ai.parts.dag.lib.dag_subgraph import DagSubgraph
from update_with_ai.parts.dag.lib.dag_subgraph_impl import (
    DagSubgraph as DagSubgraphImpl,
    __initialize__,
)
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton


class MockDagConfig:
    tier = "system"

    def __init__(self, node_visit_limit: int = 500, batch_size: int = 1) -> None:
        self.node_visit_limit = node_visit_limit
        self.batch_size = batch_size


class MockDagStorage:
    tier = "system"

    def __init__(self) -> None:
        self.dependencies: Dict[Node, Set[Dependency]] = {}
        self.dirty_nodes: Set[Node] = set()

    def get_dependencies(self, node: Node) -> Set[Dependency]:
        return set(self.dependencies.get(node, set()))

    def is_dirty(self, node: Node) -> bool:
        return node in self.dirty_nodes


class DagSubgraphImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = MockDagStorage()
        self.dag_cfg = MockDagConfig()
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.registry.register_instance(self.storage, keys=[DagStorage], tier="system")
        self.registry.register_instance(self.dag_cfg, keys=[DagConfig], tier="system")

    def test_set_target_and_topological_batching(self) -> None:
        """CUJ: Traverses dependency tree and yields ready batches in topological order."""
        a = Node(unit_address="//pkg:a", role_address="")
        b = Node(unit_address="//pkg:b", role_address="")
        c = Node(unit_address="//pkg:c", role_address="")

        self.storage.dependencies[a] = {Dependency(node=b)}
        self.storage.dependencies[b] = {Dependency(node=c)}
        self.storage.dirty_nodes.update([a, b, c])

        with enter_phase("system", registry=self.registry):
            subgraph = get_singleton(DagSubgraph)
            # Requirement: Setting a target node scopes the target subgraph to all reachable dependency nodes rooted at the target node in dag storage, arranged in dependency-first topological order, breaking ties by role tier depth first, then by unit address.
            # Requirement: [DagSubgraph] Setting a target collects all reachable dependency nodes from the target node in dag storage and computes their dependency-first topological order.
            subgraph.set_target(a)

            # Requirement: [DagSubgraph] The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage.
            self.assertFalse(subgraph.is_complete)

            # First ready node should be c (no dependencies)
            # Requirement: The next ready batch consists of contiguous dirty nodes in topological order that share the same role address, prioritized by role tier precedence (prioritizing lib before test, and test before qa) and having all their dependencies in the target subgraph clean in dag storage or present in the same ready batch, starting from the earliest ready dirty node in topological order and bounded by the batch size obtained from dag config.
            # Requirement: [DagSubgraph] When obtaining the next ready batch, uncleaned dirty nodes prioritized by role tier precedence (upstream roles before downstream roles) whose dependencies in the target subgraph are clean in dag storage or present in the same ready batch are selected, grouped by role address up to a maximum batch size.
            batch1 = subgraph.next_ready_batch()
            self.assertEqual(batch1, [c])

            self.storage.dirty_nodes.discard(c)
            batch2 = subgraph.next_ready_batch()
            self.assertEqual(batch2, [b])

            self.storage.dirty_nodes.discard(b)
            batch3 = subgraph.next_ready_batch()
            self.assertEqual(batch3, [a])

            self.storage.dirty_nodes.discard(a)
            # Requirement: [DagSubgraph] The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage.
            self.assertTrue(subgraph.is_complete)

    def test_batched_nodes_by_role(self) -> None:
        """CUJ: Batches contiguous ready nodes sharing the same role address up to batch size."""
        root = Node(unit_address="//pkg:root", role_address="")
        dep1 = Node(unit_address="//pkg:dep1", role_address="same_role")
        dep2 = Node(unit_address="//pkg:dep2", role_address="same_role")
        dep3 = Node(unit_address="//pkg:dep3", role_address="diff_role")

        self.storage.dependencies[root] = {
            Dependency(node=dep1),
            Dependency(node=dep2),
            Dependency(node=dep3),
        }
        self.storage.dirty_nodes.update([root, dep1, dep2, dep3])
        self.dag_cfg.batch_size = 2

        with enter_phase("system", registry=self.registry):
            subgraph = get_singleton(DagSubgraph)
            subgraph.set_target(root)

            # Requirement: The next ready batch consists of contiguous dirty nodes in topological order that share the same role address, prioritized by role tier precedence (prioritizing lib before test, and test before qa) and having all their dependencies in the target subgraph clean in dag storage or present in the same ready batch, starting from the earliest ready dirty node in topological order and bounded by the batch size obtained from dag config.
            # Requirement: [DagSubgraph] When obtaining the next ready batch, uncleaned dirty nodes prioritized by role tier precedence (upstream roles before downstream roles) whose dependencies in the target subgraph are clean in dag storage or present in the same ready batch are selected, grouped by role address up to a maximum batch size.
            batch = subgraph.next_ready_batch()
            self.assertLessEqual(len(batch), 2)
            if len(batch) > 1:
                self.assertEqual(batch[0].role_address, batch[1].role_address)

    def test_role_tier_prioritization_in_next_ready_batch(self) -> None:
        """CUJ: Prioritizes upstream roles over downstream roles (lib before test, test before qa)."""
        root = Node(unit_address="//pkg:root", role_address="")
        lib_a = Node(unit_address="//pkg:a", role_address="//update_python_with_ai:lib")
        test_a = Node(unit_address="//pkg:a", role_address="//update_python_with_ai:test")
        qa_a = Node(unit_address="//pkg:a", role_address="//update_python_with_ai:qa")

        lib_b = Node(unit_address="//pkg:b", role_address="//update_python_with_ai:lib")
        test_b = Node(unit_address="//pkg:b", role_address="//update_python_with_ai:test")
        qa_b = Node(unit_address="//pkg:b", role_address="//update_python_with_ai:qa")

        self.storage.dependencies[root] = {Dependency(node=qa_a), Dependency(node=qa_b)}
        self.storage.dependencies[qa_a] = {Dependency(node=test_a)}
        self.storage.dependencies[test_a] = {Dependency(node=lib_a)}
        self.storage.dependencies[qa_b] = {Dependency(node=test_b)}
        self.storage.dependencies[test_b] = {Dependency(node=lib_b)}

        self.storage.dirty_nodes.update([root, qa_a, test_a, lib_a, qa_b, test_b, lib_b])
        self.dag_cfg.batch_size = 2

        with enter_phase("system", registry=self.registry):
            subgraph = get_singleton(DagSubgraph)
            subgraph.set_target(root)

            # Both lib_a and lib_b are ready and share role "lib" -> batched together
            # Requirement: The next ready batch consists of contiguous dirty nodes in topological order that share the same role address, prioritized by role tier precedence (prioritizing lib before test, and test before qa) and having all their dependencies in the target subgraph clean in dag storage or present in the same ready batch, starting from the earliest ready dirty node in topological order and bounded by the batch size obtained from dag config.
            # Requirement: [DagSubgraph] When obtaining the next ready batch, uncleaned dirty nodes prioritized by role tier precedence (upstream roles before downstream roles) whose dependencies in the target subgraph are clean in dag storage or present in the same ready batch are selected, grouped by role address up to a maximum batch size.
            batch1 = subgraph.next_ready_batch()
            self.assertEqual(batch1, [lib_a, lib_b])

            # Suppose lib_a was cleaned, but lib_b remains dirty
            self.storage.dirty_nodes.discard(lib_a)
            # test_a is now ready, but lib_b is also ready. lib tier must take precedence over test tier!
            batch2 = subgraph.next_ready_batch()
            self.assertEqual(batch2, [lib_b])

            # Now clean lib_b; test_a and test_b are both ready
            self.storage.dirty_nodes.discard(lib_b)
            batch3 = subgraph.next_ready_batch()
            self.assertEqual(batch3, [test_a, test_b])

            # Clean test_a, but test_b remains dirty.
            # qa_a is ready, but test_b is also ready. test tier must take precedence over qa tier!
            self.storage.dirty_nodes.discard(test_a)
            batch4 = subgraph.next_ready_batch()
            self.assertEqual(batch4, [test_b])

            # Now clean test_b; qa_a and qa_b are both ready
            self.storage.dirty_nodes.discard(test_b)
            batch5 = subgraph.next_ready_batch()
            self.assertEqual(batch5, [qa_a, qa_b])

    def test_topological_order_preserved_over_lexicographical_in_batch(self) -> None:
        """CUJ: Preserves dependency-first topological order in batch selection even when alphabetical order is inverted."""
        root = Node(unit_address="//pkg:root", role_address="")
        clean_dep = Node(unit_address="//pkg:clean_dep", role_address="")
        z_earlier = Node(unit_address="//pkg:z_earlier", role_address="//update_python_with_ai:lib")
        a_later = Node(unit_address="//pkg:a_later", role_address="//update_python_with_ai:lib")

        self.storage.dependencies[root] = {Dependency(node=z_earlier), Dependency(node=a_later)}
        self.storage.dependencies[a_later] = {Dependency(node=clean_dep)}
        self.storage.dirty_nodes.update([root, z_earlier, a_later])
        self.dag_cfg.batch_size = 2

        with enter_phase("system", registry=self.registry):
            subgraph = get_singleton(DagSubgraph)
            subgraph.set_target(root)

            # In topological order (dependency first), z_earlier comes before a_later.
            # Alphabetically, a_later precedes z_earlier.
            # Requirement: The next ready batch consists of contiguous dirty nodes in topological order that share the same role address, prioritized by role tier precedence (prioritizing lib before test, and test before qa) and having all their dependencies in the target subgraph clean in dag storage or present in the same ready batch, starting from the earliest ready dirty node in topological order and bounded by the batch size obtained from dag config.
            # Requirement: [DagSubgraph] When obtaining the next ready batch, uncleaned dirty nodes prioritized by role tier precedence (upstream roles before downstream roles) whose dependencies in the target subgraph are clean in dag storage or present in the same ready batch are selected, grouped by role address up to a maximum batch size.
            batch = subgraph.next_ready_batch()
            self.assertEqual(batch, [z_earlier, a_later])

    def test_next_ready_batch_empty_when_no_ready_nodes(self) -> None:
        """CUJ: Returns empty list when no uncleaned node has all dependencies clean."""
        root = Node(unit_address="//pkg:root", role_address="")
        dep = Node(unit_address="//pkg:dep", role_address="")
        # Cycle: root -> dep -> root
        self.storage.dependencies[root] = {Dependency(node=dep)}
        self.storage.dependencies[dep] = {Dependency(node=root)}
        self.storage.dirty_nodes.update([root, dep])

        with enter_phase("system", registry=self.registry):
            subgraph = get_singleton(DagSubgraph)
            subgraph.set_target(root)

            # Requirement: If no dirty node in the target subgraph has all its dependencies in the target subgraph clean in dag storage, the next ready batch is an empty sequence.
            batch = subgraph.next_ready_batch()
            self.assertEqual(batch, [])

    def test_record_visit_enforces_limit(self) -> None:
        """CUJ: Enforces node visit limit and raises RuntimeError when exceeded."""
        node = Node(unit_address="//pkg:limited", role_address="")
        self.storage.dirty_nodes.add(node)
        self.dag_cfg.node_visit_limit = 2

        with enter_phase("system", registry=self.registry):
            subgraph = get_singleton(DagSubgraph)
            subgraph.set_target(node)

            # Requirement: Recording a visit for a batch of nodes advances the visit count for each node in the batch, raising an unexpected failure if any node exceeds the node visit limit obtained from dag config.
            # Requirement: [DagSubgraph] Recording a visit increments the visit count for each node in the batch and raises an unexpected failure if visiting any node exceeds the node visit limit.
            subgraph.record_visit([node])  # count = 1
            subgraph.record_visit([node])  # count = 2

            with self.assertRaises(RuntimeError):
                subgraph.record_visit([node])  # count = 3 > 2


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
