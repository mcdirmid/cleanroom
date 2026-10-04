"""Unit tests for loop_cleaner_impl aligned with grounding specifications."""

import unittest
from typing import List, Sequence
from update_with_ai.parts.loop.lib.loop_cleaner import LoopCleaner
from update_with_ai.parts.loop.lib.loop_cleaner_impl import (
    LoopCleaner as LoopCleanerImpl,
    __initialize__,
)
from update_with_ai.parts.loop.lib.loop_node_cleaner import NodeCleaner
from update_with_ai.parts.dag.lib.dag_storage import DagNode, RoleAddress, UnitAddress
from update_with_ai.parts.dag.lib.dag_subgraph import DagSubgraph
from support.lib.lifecycle import LifecycleRegistry, enter_phase, get_singleton


def _make_dag_node(unit_address: str, role_address: str = "") -> DagNode:
    return DagNode(unit_address=UnitAddress(unit_address), role_address=RoleAddress(role_address))


class _BoolCallable:
    def __init__(self, val: bool) -> None:
        self.val = val

    def __call__(self) -> bool:
        return self.val

    def __bool__(self) -> bool:
        return self.val


class MockDagSubgraph:
    tier = "system"

    def __init__(self, batches: List[List[DagNode]]) -> None:
        self.target: DagNode | None = None
        self.batches = list(batches)
        self.recorded_visits: List[List[DagNode]] = []

    def set_target(self, root: DagNode) -> None:
        self.target = root

    @property
    def is_complete(self) -> _BoolCallable:
        return _BoolCallable(len(self.batches) == 0)

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
        root = _make_dag_node("//pkg:root")
        node_b = _make_dag_node("//pkg:dep")
        subgraph = MockDagSubgraph(batches=[[node_b], [root]])
        cleaner = MockNodeCleaner(returns_continue=True)

        self.registry.register_instance(subgraph, keys=[DagSubgraph], tier="system")

        with enter_phase("system", registry=self.registry):
            loop_cleaner = get_singleton(LoopCleaner)
            # Requirement: MUST set target node on dag subgraph to determine dependency-first topological order.
            # Requirement: MUST process ready batches of dirty nodes in topological order, recording visits for each cleaned batch.
            # Requirement: WHEN dag subgraph is complete, MUST return true.
            # Requirement: MUST clean dirty nodes in dependency-first topological order.
            # Requirement: MUST ensure all dependencies of a node are clean before that node is cleaned.
            # Requirement: WHEN all nodes in the target subgraph are clean, MUST return true.
            result = loop_cleaner.clean(root, cleaner)

            self.assertTrue(result)
            self.assertEqual(subgraph.target, root)
            self.assertEqual(cleaner.cleaned_batches, [[node_b], [root]])
            self.assertEqual(subgraph.recorded_visits, [[node_b], [root]])
            self.assertTrue(subgraph.is_complete)

    def test_clean_halts_when_cleaner_cannot_continue(self) -> None:
        """CUJ: Cleaning halts immediately when node cleaner returns False."""
        root = _make_dag_node("//pkg:root")
        node_b = _make_dag_node("//pkg:dep")
        subgraph = MockDagSubgraph(batches=[[node_b], [root]])
        cleaner = MockNodeCleaner(returns_continue=False)

        self.registry.register_instance(subgraph, keys=[DagSubgraph], tier="system")

        with enter_phase("system", registry=self.registry):
            loop_cleaner = get_singleton(LoopCleaner)
            # Requirement: WHEN node cleaner communicates that processing cannot continue, MUST halt immediately.
            # Requirement: WHEN the node cleaner communicates that processing cannot continue, MUST halt.
            result = loop_cleaner.clean(root, cleaner)

            self.assertFalse(result)
            self.assertEqual(cleaner.cleaned_batches, [[node_b]])
            self.assertFalse(subgraph.is_complete)

    def test_clean_already_complete(self) -> None:
        """CUJ: Cleaning an already complete subgraph executes zero batches."""
        root = _make_dag_node("//pkg:root")
        subgraph = MockDagSubgraph(batches=[])
        cleaner = MockNodeCleaner(returns_continue=True)

        self.registry.register_instance(subgraph, keys=[DagSubgraph], tier="system")

        with enter_phase("system", registry=self.registry):
            loop_cleaner = get_singleton(LoopCleaner)
            # Requirement: MUST set target node on dag subgraph to determine dependency-first topological order.
            # Requirement: WHEN dag subgraph is complete, MUST return true.
            # Requirement: WHEN all nodes in the target subgraph are clean, MUST return true.
            result = loop_cleaner.clean(root, cleaner)

            self.assertTrue(result)
            self.assertEqual(subgraph.target, root)
            self.assertEqual(len(cleaner.cleaned_batches), 0)


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
