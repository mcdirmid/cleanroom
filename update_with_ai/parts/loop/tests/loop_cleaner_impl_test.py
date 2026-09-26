"""Unit tests for loop_cleaner_impl aligned with grounding specifications."""

import unittest
from typing import List, Sequence
from update_with_ai.parts.loop.lib.loop_cleaner import LoopCleaner
from update_with_ai.parts.loop.lib.loop_cleaner_impl import (
    LoopCleaner as LoopCleanerImpl,
    __initialize__,
)
from update_with_ai.parts.loop.lib.loop_node_cleaner import NodeCleaner
from update_with_ai.parts.dag.lib.dag_storage import DagNode
from update_with_ai.parts.dag.lib.dag_subgraph import DagSubgraph
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton


class MockDagSubgraph:
    tier = "system"

    def __init__(self, batches: List[List[DagNode]]) -> None:
        self.target: DagNode | None = None
        self.batches = list(batches)
        self.recorded_visits: List[List[DagNode]] = []

    def set_target(self, root: DagNode) -> None:
        self.target = root

    @property
    def is_complete(self) -> bool:
        return len(self.batches) == 0

    def next_ready_batch(self) -> List[DagNode]:
        if self.batches:
            return self.batches.pop(0)
        return []

    def record_visit(self, nodes: Sequence[DagNode]) -> None:
        self.recorded_visits.append(list(nodes))


class MockNodeCleaner:
    tier = "system"

    def __init__(self, returns_continue: bool = True) -> None:
        self.cleaned_batches: List[List[DagNode]] = []
        self.returns_continue = returns_continue

    def clean(self, nodes: Sequence[DagNode]) -> bool:
        self.cleaned_batches.append(list(nodes))
        return self.returns_continue


class LoopCleanerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

    def test_clean_success(self) -> None:
        """CUJ: Iterative topological cleaning over batches to completion."""
        root = DagNode(unit_address="//pkg:root")
        node_b = DagNode(unit_address="//pkg:dep")
        subgraph = MockDagSubgraph(batches=[[node_b], [root]])
        cleaner = MockNodeCleaner(returns_continue=True)

        self.registry.register_instance(subgraph, keys=[DagSubgraph], tier="system")

        with enter_phase("system", registry=self.registry):
            loop_cleaner = get_singleton(LoopCleaner)
            # Requirement: Target node scoping sets the target node on the dag subgraph to determine dependency-first topological order.
            # Requirement: Cleaning processes ready batches of dirty nodes in topological order, recording node visits for each cleaned batch, and halts immediately if the node cleaner communicates that processing cannot continue.
            # Requirement: [LoopCleaner] Cleaning dirty nodes halts if the node cleaner communicates that processing cannot continue.
            # Requirement: [LoopCleaner] Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
            # Requirement: Cleaning concludes when the dag subgraph is complete, indicating all reachable nodes in the target subgraph are clean.
            # Requirement: [LoopCleaner] Cleaning concludes when all nodes in the subgraph rooted at the node are clean.
            loop_cleaner.clean(root, cleaner)

            self.assertEqual(subgraph.target, root)
            self.assertEqual(cleaner.cleaned_batches, [[node_b], [root]])
            self.assertEqual(subgraph.recorded_visits, [[node_b], [root]])
            self.assertTrue(subgraph.is_complete)

    def test_clean_halts_when_cleaner_cannot_continue(self) -> None:
        """CUJ: Cleaning halts immediately when node cleaner returns False."""
        root = DagNode(unit_address="//pkg:root")
        node_b = DagNode(unit_address="//pkg:dep")
        subgraph = MockDagSubgraph(batches=[[node_b], [root]])
        cleaner = MockNodeCleaner(returns_continue=False)

        self.registry.register_instance(subgraph, keys=[DagSubgraph], tier="system")

        with enter_phase("system", registry=self.registry):
            loop_cleaner = get_singleton(LoopCleaner)
            # Requirement: Cleaning processes ready batches of dirty nodes in topological order, recording node visits for each cleaned batch, and halts immediately if the node cleaner communicates that processing cannot continue.
            # Requirement: [LoopCleaner] Cleaning dirty nodes halts if the node cleaner communicates that processing cannot continue.
            loop_cleaner.clean(root, cleaner)

            self.assertEqual(cleaner.cleaned_batches, [[node_b]])
            self.assertFalse(subgraph.is_complete)

    def test_clean_already_complete(self) -> None:
        """CUJ: Cleaning an already complete subgraph executes zero batches."""
        root = DagNode(unit_address="//pkg:root")
        subgraph = MockDagSubgraph(batches=[])
        cleaner = MockNodeCleaner(returns_continue=True)

        self.registry.register_instance(subgraph, keys=[DagSubgraph], tier="system")

        with enter_phase("system", registry=self.registry):
            loop_cleaner = get_singleton(LoopCleaner)
            # Requirement: Target node scoping sets the target node on the dag subgraph to determine dependency-first topological order.
            # Requirement: Cleaning concludes when the dag subgraph is complete, indicating all reachable nodes in the target subgraph are clean.
            loop_cleaner.clean(root, cleaner)

            self.assertEqual(subgraph.target, root)
            self.assertEqual(len(cleaner.cleaned_batches), 0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
