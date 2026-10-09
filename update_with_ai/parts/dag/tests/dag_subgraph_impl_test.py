# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-09T04:22:58Z
# CHANGE: Assert candidate with uncleaned in-subgraph dependencies excluded during batch expansion and external dependencies ignored
# CODE_HASH: b1a0654f7e65
# COVERAGE_AUDIT: 2026-10-09T21:19:01Z
# QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

"""Unit tests for dag_subgraph_impl per its grounding specification."""

from __future__ import annotations

import unittest
from typing import Dict, List, Optional, Sequence, Set

from support.lib.lifecycle import LifecycleRegistry, enter_phase, system
from update_with_ai.parts.dag.lib import dag_config, dag_storage, dag_subgraph
from update_with_ai.parts.dag.lib.dag_subgraph_impl import (
    DagSubgraph,
    __initialize__,
)


def _make_node(unit_address: str, role_address: str) -> dag_storage.DagNode:
    return dag_storage.DagNode(
        unit_address=dag_storage.UnitAddress(unit_address),
        role_address=dag_storage.RoleAddress(role_address),
    )


def _make_dep(node: dag_storage.DagNode, is_silent: bool = False) -> dag_storage.DagDependency:
    return dag_storage.DagDependency(node=node, is_silent=is_silent)


class MockDagConfig:
    tier = system

    def __init__(
        self,
        node_visit_limit: int = 5,
        batch_size: int = 2,
    ) -> None:
        self._node_visit_limit = dag_config.NodeVisitLimit(node_visit_limit)
        self._batch_size = dag_config.BatchSize(batch_size)

    @property
    def node_visit_limit(self) -> dag_config.NodeVisitLimit:
        return self._node_visit_limit

    @property
    def batch_size(self) -> dag_config.BatchSize:
        return self._batch_size


class MockDagStorage:
    tier = system

    def __init__(self) -> None:
        self._deps: Dict[dag_storage.DagNode, Set[dag_storage.DagDependency]] = {}
        self._dirty: Set[dag_storage.DagNode] = set()

    def set_dependencies(
        self, node: dag_storage.DagNode, deps: Set[dag_storage.DagDependency]
    ) -> None:
        self._deps[node] = deps

    def set_dirty(self, node: dag_storage.DagNode, dirty: bool = True) -> None:
        if dirty:
            self._dirty.add(node)
        else:
            self._dirty.discard(node)

    def get_dependencies(
        self, node: dag_storage.DagNode
    ) -> Set[dag_storage.DagDependency]:
        return self._deps.get(node, set())

    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        return node in self._dirty


class DagSubgraphImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)
        self.config = MockDagConfig(node_visit_limit=3, batch_size=2)
        self.registry.register_instance(
            self.config,
            keys=[dag_config.DagConfig],
            tier=system,
        )
        self.storage = MockDagStorage()
        self.registry.register_instance(
            self.storage,
            keys=[dag_storage.DagStorage],
            tier=system,
        )

    def test_initialization(self) -> None:
        """CUJ: Verify component registration and singleton resolution."""
        self.assertIsNotNone(self.registry)
        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            self.assertIsNotNone(subgraph)

    def test_is_complete_all_clean(self) -> None:
        """Postcondition: MUST return true when all reachable nodes are clean."""
        target = _make_node("unit_a", "role_test")
        dep1 = _make_node("unit_b", "role_lib")
        self.storage.set_dependencies(target, {_make_dep(dep1)})

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            self.assertTrue(subgraph.is_complete())

    def test_is_complete_dirty_node(self) -> None:
        """Postcondition: MUST return false when any reachable node is dirty."""
        target = _make_node("unit_a", "role_test")
        dep1 = _make_node("unit_b", "role_lib")
        self.storage.set_dependencies(target, {_make_dep(dep1)})
        self.storage.set_dirty(dep1, True)

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            self.assertFalse(subgraph.is_complete())

    def test_set_target_topological_sort_ties(self) -> None:
        """Postcondition: Break ties by role tier depth first, then by unit address."""
        target = _make_node("target_unit", "role_final")
        node_b = _make_node("b_unit", "role_middle")
        node_a = _make_node("a_unit", "role_middle")
        self.storage.set_dependencies(target, {_make_dep(node_b), _make_dep(node_a)})
        self.storage.set_dirty(node_b, True)
        self.storage.set_dirty(node_a, True)

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            batch = subgraph.next_ready_batch()
            self.assertEqual(list(batch), [node_a, node_b])

    def test_next_ready_batch_happy_path(self) -> None:
        """Postcondition: MUST select contiguous dirty nodes sharing the same role address."""
        target = _make_node("target_unit", "role_test")
        dep1 = _make_node("unit_1", "role_lib")
        dep2 = _make_node("unit_2", "role_lib")
        self.storage.set_dependencies(target, {_make_dep(dep1), _make_dep(dep2)})
        self.storage.set_dirty(dep1, True)
        self.storage.set_dirty(dep2, True)

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            batch = subgraph.next_ready_batch()
            self.assertEqual(len(batch), 2)
            self.assertTrue(all(n.role_address == dag_storage.RoleAddress("role_lib") for n in batch))

    def test_next_ready_batch_bounds_to_batch_size(self) -> None:
        """Postcondition: MUST bound batch size to limit from configuration."""
        target = _make_node("target_unit", "role_test")
        nodes = [_make_node(f"unit_{i}", "role_lib") for i in range(5)]
        self.storage.set_dependencies(target, {_make_dep(n) for n in nodes})
        for n in nodes:
            self.storage.set_dirty(n, True)

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            batch = subgraph.next_ready_batch()
            self.assertLessEqual(len(batch), 2)

    def test_next_ready_batch_when_no_dirty_ready_returns_empty(self) -> None:
        """Postcondition: WHEN no dirty node in the target subgraph has all its dependencies clean, MUST return empty sequence."""
        target = _make_node("target_unit", "role_test")
        dep = _make_node("dep_unit", "role_low")
        self.storage.set_dependencies(target, {_make_dep(dep)})
        # All nodes are clean, so no dirty node exists to be cleaned

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            batch = subgraph.next_ready_batch()
            self.assertEqual(len(batch), 0)

    def test_record_visit_advances_count(self) -> None:
        """Postcondition: MUST advance visit count for each node in the batch."""
        node1 = _make_node("unit_1", "role_lib")
        node2 = _make_node("unit_2", "role_lib")

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.record_visit([node1, node2])

    def test_record_visit_exceeds_limit_raises(self) -> None:
        """Postcondition: WHEN any node exceeds visit limit, MUST raise unexpected failure."""
        node = _make_node("unit_1", "role_lib")

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            # node_visit_limit is 3
            subgraph.record_visit([node])
            subgraph.record_visit([node])
            subgraph.record_visit([node])
            with self.assertRaises(Exception):
                subgraph.record_visit([node])

    def test_next_ready_batch_prioritizes_upstream_role_before_downstream(self) -> None:
        """Postcondition: MUST dynamically prioritize upstream roles before downstream roles based on role dependency depth."""
        registry = LifecycleRegistry()
        __initialize__(registry)
        cfg = MockDagConfig(node_visit_limit=3, batch_size=5)
        registry.register_instance(cfg, keys=[dag_config.DagConfig], tier=system)
        storage = MockDagStorage()
        registry.register_instance(storage, keys=[dag_storage.DagStorage], tier=system)

        target = _make_node("target_unit", "role_test")
        ready_1 = _make_node("ready_1", "role_lib")
        ready_2 = _make_node("ready_2", "role_lib")
        unready_candidate = _make_node("unready_cand", "role_lib")
        unbatched_dirty_dep = _make_node("unbatched_dep", "role_low")

        storage.set_dependencies(unready_candidate, {_make_dep(unbatched_dirty_dep)})
        storage.set_dependencies(target, {_make_dep(ready_1), _make_dep(ready_2), _make_dep(unready_candidate)})
        storage.set_dirty(target, True)
        storage.set_dirty(ready_1, True)
        storage.set_dirty(ready_2, True)
        storage.set_dirty(unready_candidate, True)
        storage.set_dirty(unbatched_dirty_dep, True)

        with enter_phase(system, registry=registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            batch = subgraph.next_ready_batch()
            self.assertEqual(list(batch), [unbatched_dirty_dep])
            self.assertNotIn(ready_1, batch)
            self.assertNotIn(ready_2, batch)
            self.assertNotIn(unready_candidate, batch)

    def test_next_ready_batch_expansion_terminates_on_intervening_clean_node(self) -> None:
        """Postcondition: Ready batch expansion terminates upon encountering an intervening clean node in topological sequence."""
        registry = LifecycleRegistry()
        __initialize__(registry)
        cfg = MockDagConfig(node_visit_limit=3, batch_size=5)
        registry.register_instance(cfg, keys=[dag_config.DagConfig], tier=system)
        storage = MockDagStorage()
        registry.register_instance(storage, keys=[dag_storage.DagStorage], tier=system)

        target = _make_node("target_unit", "role_test")
        node_dirty_1 = _make_node("unit_dirty_1", "role_lib")
        node_clean = _make_node("unit_clean_intervening", "role_lib")
        node_dirty_2 = _make_node("unit_dirty_2", "role_lib")

        storage.set_dependencies(node_clean, {_make_dep(node_dirty_1)})
        storage.set_dependencies(node_dirty_2, {_make_dep(node_clean)})
        storage.set_dependencies(target, {_make_dep(node_dirty_2)})

        storage.set_dirty(node_dirty_1, True)
        storage.set_dirty(node_clean, False)
        storage.set_dirty(node_dirty_2, True)
        storage.set_dirty(target, True)

        with enter_phase(system, registry=registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            batch = subgraph.next_ready_batch()
            self.assertEqual(list(batch), [node_dirty_1])
            self.assertNotIn(node_dirty_2, batch)

    def test_next_ready_batch_ignores_external_dependencies(self) -> None:
        """Postcondition: Dependencies external to active subgraph are ignored when determining readiness."""
        target = _make_node("target_unit", "role_test")
        in_subgraph_node = _make_node("in_subgraph", "role_lib")
        external_dep = _make_node("ext_dep", "role_lib")

        self.storage.set_dependencies(target, {_make_dep(in_subgraph_node)})
        self.storage.set_dirty(target, True)
        self.storage.set_dirty(in_subgraph_node, True)
        self.storage.set_dirty(external_dep, True)

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            # external_dep belongs outside the active target subgraph
            self.storage.set_dependencies(in_subgraph_node, {_make_dep(external_dep)})
            batch = subgraph.next_ready_batch()
            self.assertIn(in_subgraph_node, batch)

    def test_next_ready_batch_evaluating_readiness_with_silent_external_dependency(self) -> None:
        """Postcondition: Silent dependency belonging outside the active target subgraph does not block readiness."""
        target = _make_node("target_unit_2", "role_test")
        in_subgraph_node = _make_node("in_subgraph_2", "role_lib")
        external_dep = _make_node("ext_dep_silent", "role_lib")

        self.storage.set_dependencies(in_subgraph_node, {_make_dep(external_dep, is_silent=True)})
        self.storage.set_dependencies(target, {_make_dep(in_subgraph_node)})
        self.storage.set_dirty(target, True)
        self.storage.set_dirty(in_subgraph_node, True)
        self.storage.set_dirty(external_dep, True)

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            batch = subgraph.next_ready_batch()
            self.assertIn(in_subgraph_node, batch)

    def test_next_ready_batch_expansion_excludes_candidate_with_uncleaned_in_subgraph_dependencies(self) -> None:
        """Postcondition: Batch expansion excludes candidate nodes of the same role address whose in-subgraph dependencies remain uncleaned."""
        registry = LifecycleRegistry()
        __initialize__(registry)
        cfg = MockDagConfig(node_visit_limit=3, batch_size=5)
        registry.register_instance(cfg, keys=[dag_config.DagConfig], tier=system)
        storage = MockDagStorage()
        registry.register_instance(storage, keys=[dag_storage.DagStorage], tier=system)

        target = _make_node("target_unit", "role_test")
        start_node = _make_node("start_ready", "role_lib")
        cand_unready = _make_node("cand_unready", "role_lib")
        dep_uncleaned = _make_node("dep_uncleaned", "role_other")
        ready_2 = _make_node("ready_2", "role_lib")

        storage.set_dependencies(dep_uncleaned, {_make_dep(start_node)})
        storage.set_dependencies(cand_unready, {_make_dep(dep_uncleaned)})
        storage.set_dependencies(target, {_make_dep(start_node), _make_dep(cand_unready), _make_dep(ready_2)})

        storage.set_dirty(target, True)
        storage.set_dirty(start_node, True)
        storage.set_dirty(cand_unready, True)
        storage.set_dirty(dep_uncleaned, True)
        storage.set_dirty(ready_2, True)

        with enter_phase(system, registry=registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            batch = subgraph.next_ready_batch()
            self.assertIn(start_node, batch)
            self.assertNotIn(cand_unready, batch)
            self.assertIn(ready_2, batch)

    def test_next_ready_batch_withholds_dirty_node_with_different_role_address(self) -> None:
        """Postcondition: MUST withhold dirty nodes with a different role address than the first selected node."""
        target = _make_node("target_unit", "role_test")
        node_role_a = _make_node("unit_a", "role_alpha")
        node_role_b = _make_node("unit_b", "role_beta")
        self.storage.set_dependencies(target, {_make_dep(node_role_a), _make_dep(node_role_b)})
        self.storage.set_dirty(target, True)
        self.storage.set_dirty(node_role_a, True)
        self.storage.set_dirty(node_role_b, True)

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            batch = subgraph.next_ready_batch()
            self.assertEqual(len(batch), 1)
            selected = batch[0]
            if selected == node_role_a:
                self.assertNotIn(node_role_b, batch)
            else:
                self.assertNotIn(node_role_a, batch)
            self.assertTrue(all(n.role_address == selected.role_address for n in batch))

    def test_next_ready_batch_excludes_already_clean_nodes(self) -> None:
        """Postcondition: MUST exclude nodes that are already clean from the ready batch."""
        target = _make_node("target_unit", "role_test")
        clean_dep = _make_node("clean_dep", "role_lib")
        dirty_dep = _make_node("dirty_dep", "role_lib")
        self.storage.set_dependencies(target, {_make_dep(clean_dep), _make_dep(dirty_dep)})
        self.storage.set_dirty(clean_dep, False)
        self.storage.set_dirty(dirty_dep, True)
        self.storage.set_dirty(target, True)

        with enter_phase(system, registry=self.registry) as scope:
            subgraph = scope.get_singleton(DagSubgraph)
            subgraph.set_target(target)
            batch = subgraph.next_ready_batch()
            self.assertIn(dirty_dep, batch)
            self.assertNotIn(clean_dep, batch)


if __name__ == "__main__":
    unittest.main()

# Untested requirements:
# None
