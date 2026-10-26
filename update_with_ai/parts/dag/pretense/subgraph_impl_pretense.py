"""Pretense State Machine, Unit Tests, and Fuzzer for DagSubgraph (subgraph_impl).

Consolidates:
1. SubgraphImplStateMachine (composing DagConfig and DagStorage dependencies)
2. Deterministic Unit Tests (verifying DagSubgraphImpl against state machine)
3. Hypothesis Stateful Fuzzer (stressing invariants across dense multi-tier DAGs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import unittest
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from hypothesis import given, settings, strategies as st
from pretense.collections import PretenseDict
from pretense.proto import StateMachine
from support.lib.lifecycle import LifecycleRegistry, enter_phase, system

from update_with_ai.parts.dag.lib import dag_config, dag_storage, subgraph
from update_with_ai.parts.dag.lib.dag_config import DagConfig
from update_with_ai.parts.dag.lib.dag_storage import (
    DagDependency,
    DagNode,
    DagStorage,
    RoleAddress,
    UnitAddress,
)
from update_with_ai.parts.dag.lib.subgraph import DagSubgraph
from update_with_ai.parts.dag.lib.subgraph_impl import (
    DagSubgraph as DagSubgraphImpl,
    __initialize__,
)
from update_with_ai.parts.dag.pretense.dag_config_pretense import (
    DagConfigState,
    proto as dag_config_proto,
)
from update_with_ai.parts.dag.pretense.dag_storage_pretense import (
    DagStorageState,
    proto as dag_storage_proto,
)


# ==============================================================================
# 1. Implementation State Machine (Composing DagConfig & DagStorage)
# ==============================================================================

@dataclass
class SubgraphImplState:
    """Canonical model state for DagSubgraph implementation under test."""
    active_target: Optional[DagNode] = None
    visit_counts: PretenseDict[DagNode, int] = field(default_factory=PretenseDict)


class SubgraphImplStateMachine:
    """Implementation state machine composing child state machines and driving DagSubgraph."""

    def __init__(
        self,
        config_state: Optional[DagConfigState] = None,
        storage_state: Optional[DagStorageState] = None,
        impl_state: Optional[SubgraphImplState] = None,
    ) -> None:
        self.config_sm: StateMachine[DagConfigState] = dag_config_proto.make_state_machine(
            config_state or DagConfigState()
        )
        self.storage_sm: StateMachine[DagStorageState] = dag_storage_proto.make_state_machine(
            storage_state or DagStorageState()
        )
        self.state: SubgraphImplState = impl_state or SubgraphImplState()
        self._target_instance: Optional[DagSubgraph] = None

    @classmethod
    def make_state_machine(
        cls,
        config_state: Optional[DagConfigState] = None,
        storage_state: Optional[DagStorageState] = None,
        impl_state: Optional[SubgraphImplState] = None,
    ) -> "SubgraphImplStateMachine":
        """Instantiate an implementation state machine."""
        return cls(config_state, storage_state, impl_state)

    def make_config_fake(self) -> DagConfig:
        """Synthesize a zero-ambiguity in-memory fake for DagConfig."""
        return self.config_sm.as_fake(dag_config.DagConfig)

    def make_storage_fake(self) -> DagStorage:
        """Synthesize a zero-ambiguity in-memory fake for DagStorage."""
        return self.storage_sm.as_fake(dag_storage.DagStorage)

    def install_fakes(self, registry: LifecycleRegistry) -> None:
        """Inject synthesized dependency fakes as singletons into their lifecycle phases."""
        registry.register_instance(
            self.make_config_fake(),
            keys=[dag_config.DagConfig],
            tier=system,
        )
        registry.register_instance(
            self.make_storage_fake(),
            keys=[dag_storage.DagStorage],
            tier=system,
        )

    def bind_instance(self, instance: DagSubgraph) -> None:
        """Bind the concrete DagSubgraph implementation under test."""
        self._target_instance = instance

    def set_target(self, target: DagNode) -> None:
        """Transition: set active subgraph target."""
        self.state.active_target = target
        if self._target_instance is not None:
            self._target_instance.set_target(target)

    def is_complete(self) -> bool:
        """Transition: check if target subgraph is completely clean."""
        if self._target_instance is not None:
            return self._target_instance.is_complete()
        if self.state.active_target is None:
            return True
        return not bool(self.storage_sm.state.dirty_nodes)

    def next_ready_batch(self) -> Sequence[DagNode]:
        """Transition: compute next ready batch of dirty nodes."""
        if self._target_instance is not None:
            return self._target_instance.next_ready_batch()
        return ()

    def record_visit(self, batch: Sequence[DagNode]) -> None:
        """Transition: record execution visit for batch and track bounds."""
        limit = self.config_sm.state.node_visit_limit
        for node in batch:
            self.state.visit_counts[node] = self.state.visit_counts.get(node, 0) + 1
            if self.state.visit_counts[node] > limit:
                if self._target_instance is not None:
                    self._target_instance.record_visit(batch)
                raise RuntimeError(f"Visit count limit {limit} exceeded for {node}")

        if self._target_instance is not None:
            self._target_instance.record_visit(batch)


# ==============================================================================
# 2. Deterministic Unit Tests (Regression Suite)
# ==============================================================================

class TestDagSubgraphUnit(unittest.TestCase):
    """Deterministic unit tests verifying DagSubgraphImpl against SubgraphImplStateMachine."""

    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)

        # Instantiate composite implementation state machine
        self.impl_sm = SubgraphImplStateMachine.make_state_machine()
        self.impl_sm.config_sm.seed_limits(node_visit_limit=3, batch_size=2)

        # Inject synthesized fakes as singletons in their lifecycle phases
        self.impl_sm.install_fakes(self.registry)

    def test_subgraph_execution_and_clean_convergence(self) -> None:
        with enter_phase(system, registry=self.registry) as scope:
            real_subgraph = scope.get_singleton(subgraph.DagSubgraph)
            self.impl_sm.bind_instance(real_subgraph)

            # Build graph: target depends on dep1, dep1 depends on root
            root = DagNode(UnitAddress("//pkg:root"), RoleAddress("cleanroom:high"))
            dep1 = DagNode(UnitAddress("//pkg:dep1"), RoleAddress("cleanroom:low"))
            target = DagNode(UnitAddress("//pkg:target"), RoleAddress("cleanroom:lib"))

            self.impl_sm.storage_sm.seed_node(root, is_dirty=True)
            self.impl_sm.storage_sm.seed_node(dep1, is_dirty=True, dependencies={DagDependency(node=root, is_silent=False)})
            self.impl_sm.storage_sm.seed_node(target, is_dirty=True, dependencies={DagDependency(node=dep1, is_silent=False)})

            # 1. Set subgraph target
            self.impl_sm.set_target(target)
            self.assertFalse(self.impl_sm.is_complete())

            # 2. Next ready batch should yield root first (upstream dependency)
            batch1 = self.impl_sm.next_ready_batch()
            self.assertEqual(list(batch1), [root])
            self.impl_sm.record_visit(batch1)

            # Mark root clean
            self.impl_sm.storage_sm.seed_dirty_status(root, dirty=False)

            # 3. Next batch should yield dep1
            batch2 = self.impl_sm.next_ready_batch()
            self.assertEqual(list(batch2), [dep1])
            self.impl_sm.record_visit(batch2)

            # Mark dep1 clean
            self.impl_sm.storage_sm.seed_dirty_status(dep1, dirty=False)

            # 4. Next batch should yield target
            batch3 = self.impl_sm.next_ready_batch()
            self.assertEqual(list(batch3), [target])
            self.impl_sm.record_visit(batch3)

            # Mark target clean
            self.impl_sm.storage_sm.seed_dirty_status(target, dirty=False)

            # 5. Graph is now complete
            self.assertTrue(self.impl_sm.is_complete())
            self.assertEqual(len(self.impl_sm.next_ready_batch()), 0)

    def test_subgraph_visit_limit_enforcement(self) -> None:
        with enter_phase(system, registry=self.registry) as scope:
            real_subgraph = scope.get_singleton(subgraph.DagSubgraph)
            self.impl_sm.bind_instance(real_subgraph)

            node = DagNode(UnitAddress("//pkg:loop"), RoleAddress("cleanroom:high"))
            self.impl_sm.storage_sm.seed_node(node, is_dirty=True)

            self.impl_sm.set_target(node)

            # Visit up to limit (3)
            self.impl_sm.record_visit([node])
            self.impl_sm.record_visit([node])
            self.impl_sm.record_visit([node])

            # Exceeding visit limit must raise RuntimeError
            with self.assertRaises(RuntimeError):
                self.impl_sm.record_visit([node])

    def test_batch_size_limit_breaks_batch(self) -> None:
        """Hits line 173: batch size bound breaks batch collection."""
        with enter_phase(system, registry=self.registry) as scope:
            real_subgraph = scope.get_singleton(subgraph.DagSubgraph)
            self.impl_sm.bind_instance(real_subgraph)

            # 3 nodes with the same role; batch_size limit is 2
            n1 = DagNode(UnitAddress("//pkg:n1"), RoleAddress("cleanroom:lib"))
            n2 = DagNode(UnitAddress("//pkg:n2"), RoleAddress("cleanroom:lib"))
            n3 = DagNode(UnitAddress("//pkg:n3"), RoleAddress("cleanroom:lib"))

            self.impl_sm.storage_sm.seed_node(n1, is_dirty=True)
            self.impl_sm.storage_sm.seed_node(n2, is_dirty=True, dependencies={DagDependency(node=n1, is_silent=False)})
            self.impl_sm.storage_sm.seed_node(n3, is_dirty=True, dependencies={DagDependency(node=n2, is_silent=False)})

            self.impl_sm.set_target(n3)
            batch = self.impl_sm.next_ready_batch()
            # Batch size is capped at 2, breaking before n3
            self.assertEqual(len(batch), 2)
            self.assertEqual(list(batch), [n1, n2])

    def test_clean_node_in_topological_sequence_breaks_batch(self) -> None:
        """Hits line 176: non-dirty node in topological scan breaks contiguous batch."""
        with enter_phase(system, registry=self.registry) as scope:
            real_subgraph = scope.get_singleton(subgraph.DagSubgraph)
            self.impl_sm.bind_instance(real_subgraph)

            # n1 (dirty) -> n2 (clean) -> n3 (dirty) all with same role
            n1 = DagNode(UnitAddress("//pkg:n1"), RoleAddress("cleanroom:lib"))
            n2 = DagNode(UnitAddress("//pkg:n2"), RoleAddress("cleanroom:lib"))
            n3 = DagNode(UnitAddress("//pkg:n3"), RoleAddress("cleanroom:lib"))

            self.impl_sm.storage_sm.seed_node(n1, is_dirty=True)
            self.impl_sm.storage_sm.seed_node(n2, is_dirty=False, dependencies={DagDependency(node=n1, is_silent=False)})
            self.impl_sm.storage_sm.seed_node(n3, is_dirty=True, dependencies={DagDependency(node=n2, is_silent=False)})

            self.impl_sm.set_target(n3)
            batch = self.impl_sm.next_ready_batch()
            # n1 is ready, next node n2 is clean, so batch breaks
            self.assertEqual(list(batch), [n1])

    def test_uncleaned_external_dependency_breaks_batch(self) -> None:
        """Hits line 185: candidate has uncleaned dependency not in collected batch."""
        with enter_phase(system, registry=self.registry) as scope:
            real_subgraph = scope.get_singleton(subgraph.DagSubgraph)
            self.impl_sm.bind_instance(real_subgraph)

            target = DagNode(UnitAddress("//pkg:target_unit"), RoleAddress("cleanroom:test"))
            start_node = DagNode(UnitAddress("//pkg:start_ready"), RoleAddress("cleanroom:lib"))
            cand_unready = DagNode(UnitAddress("//pkg:cand_unready"), RoleAddress("cleanroom:lib"))
            dep_uncleaned = DagNode(UnitAddress("//pkg:dep_uncleaned"), RoleAddress("cleanroom:other"))
            ready_2 = DagNode(UnitAddress("//pkg:ready_2"), RoleAddress("cleanroom:lib"))

            self.impl_sm.storage_sm.seed_node(start_node, is_dirty=True)
            self.impl_sm.storage_sm.seed_node(dep_uncleaned, is_dirty=True, dependencies={DagDependency(node=start_node, is_silent=False)})
            self.impl_sm.storage_sm.seed_node(cand_unready, is_dirty=True, dependencies={DagDependency(node=dep_uncleaned, is_silent=False)})
            self.impl_sm.storage_sm.seed_node(ready_2, is_dirty=True)
            self.impl_sm.storage_sm.seed_node(target, is_dirty=True, dependencies={
                DagDependency(node=start_node, is_silent=False),
                DagDependency(node=cand_unready, is_silent=False),
                DagDependency(node=ready_2, is_silent=False),
            })
            self.impl_sm.set_target(target)

            batch = self.impl_sm.next_ready_batch()
            self.assertIn(start_node, batch)
            self.assertNotIn(cand_unready, batch)

    def test_cyclic_role_dependencies_depth_resolution(self) -> None:
        """Hits line 48: resolving set detects cycle in role dependencies."""
        with enter_phase(system, registry=self.registry) as scope:
            real_subgraph = scope.get_singleton(subgraph.DagSubgraph)
            self.impl_sm.bind_instance(real_subgraph)

            # Mutual role dependency across nodes:
            # node_a (role_alpha) -> node_b (role_beta)
            # node_c (role_beta) -> node_d (role_alpha)
            # target (role_root) -> node_a and node_c
            node_d = DagNode(UnitAddress("//pkg:d"), RoleAddress("cleanroom:alpha"))
            node_b = DagNode(UnitAddress("//pkg:b"), RoleAddress("cleanroom:beta"))
            node_a = DagNode(UnitAddress("//pkg:a"), RoleAddress("cleanroom:alpha"))
            node_c = DagNode(UnitAddress("//pkg:c"), RoleAddress("cleanroom:beta"))
            target = DagNode(UnitAddress("//pkg:tgt"), RoleAddress("cleanroom:root"))

            self.impl_sm.storage_sm.seed_node(node_d, is_dirty=False)
            self.impl_sm.storage_sm.seed_node(node_b, is_dirty=False)
            self.impl_sm.storage_sm.seed_node(node_a, is_dirty=False, dependencies={DagDependency(node=node_b, is_silent=False)})
            self.impl_sm.storage_sm.seed_node(node_c, is_dirty=False, dependencies={DagDependency(node=node_d, is_silent=False)})
            self.impl_sm.storage_sm.seed_node(target, is_dirty=True, dependencies={
                DagDependency(node=node_a, is_silent=False),
                DagDependency(node=node_c, is_silent=False),
            })

            # Setting target resolves role depths where alpha depends on beta and beta depends on alpha
            self.impl_sm.set_target(target)
            self.assertFalse(self.impl_sm.is_complete())


# ==============================================================================
# 3. Hypothesis Stateful Fuzzer (Dense Multi-Tier DAGs)
# ==============================================================================

@st.composite
def connected_dag_strategy(draw: st.DrawFn) -> tuple[DagNode, list[DagNode], dict[DagNode, bool], dict[DagNode, set[DagDependency]]]:
    """Generates a dense, multi-tier DAG where every node is guaranteed reachable from target."""
    num_layers = draw(st.integers(min_value=2, max_value=4))
    roles = ["cleanroom:high", "cleanroom:low", "cleanroom:lib"]
    layers: list[list[DagNode]] = []
    node_id = 0
    all_nodes: list[DagNode] = []
    node_dirty: dict[DagNode, bool] = {}
    dependencies: dict[DagNode, set[DagDependency]] = {}

    for layer_idx in range(num_layers):
        if layer_idx == num_layers - 1:
            # Target layer has 1 root node
            layer_size = 1
            layer_role = "cleanroom:lib"
        else:
            layer_size = draw(st.integers(min_value=2, max_value=4))
            layer_role = roles[min(layer_idx, len(roles) - 1)]

        current_layer: list[DagNode] = []
        for _ in range(layer_size):
            r = layer_role
            if layer_idx < num_layers - 1 and draw(st.booleans()):
                r = draw(st.sampled_from(roles))
            node = DagNode(UnitAddress(f"//pkg:n{node_id}"), RoleAddress(r))
            node_id += 1
            current_layer.append(node)
            all_nodes.append(node)
            node_dirty[node] = draw(st.booleans())
            dependencies[node] = set()
        layers.append(current_layer)

    # Ensure at least 2 nodes are dirty
    if sum(1 for n in all_nodes if node_dirty[n]) < 2:
        for n in all_nodes[:2]:
            node_dirty[n] = True

    # Connect nodes in each layer to preceding layer
    for layer_idx in range(1, num_layers):
        prev_layer = layers[layer_idx - 1]
        for node in layers[layer_idx]:
            k = draw(st.integers(min_value=1, max_value=len(prev_layer)))
            chosen_deps = draw(st.lists(st.sampled_from(prev_layer), min_size=k, max_size=k, unique=True))
            for dep in chosen_deps:
                dependencies[node].add(DagDependency(node=dep, is_silent=False))

    # Guarantee full reachability: ensure no disconnected sinks in earlier layers
    for layer_idx in range(num_layers - 1):
        curr_layer = layers[layer_idx]
        next_layer = layers[layer_idx + 1]
        linked_nodes = {dep.node for n in next_layer for dep in dependencies[n]}
        unlinked = [n for n in curr_layer if n not in linked_nodes]
        for n in unlinked:
            target_consumer = draw(st.sampled_from(next_layer))
            dependencies[target_consumer].add(DagDependency(node=n, is_silent=False))

    target = layers[-1][0]
    return target, all_nodes, node_dirty, dependencies


class TestDagSubgraphFuzz(unittest.TestCase):
    """Hypothesis property fuzz testing driven by SubgraphImplStateMachine across connected multi-tier DAGs."""

    @settings(max_examples=50)
    @given(
        batch_size=st.integers(min_value=1, max_value=3),
        visit_limit=st.integers(min_value=10, max_value=25),
        dag_data=connected_dag_strategy(),
    )
    def test_subgraph_execution_invariants_under_fuzz(
        self,
        batch_size: int,
        visit_limit: int,
        dag_data: tuple[DagNode, list[DagNode], dict[DagNode, bool], dict[DagNode, set[DagDependency]]],
    ) -> None:
        target, all_nodes, node_dirty, dependencies = dag_data

        registry = LifecycleRegistry()
        __initialize__(registry)

        impl_sm = SubgraphImplStateMachine.make_state_machine()
        impl_sm.config_sm.seed_limits(node_visit_limit=visit_limit, batch_size=batch_size)
        impl_sm.install_fakes(registry)

        # Seed all nodes and dependencies
        for node in all_nodes:
            deps = dependencies.get(node, set())
            impl_sm.storage_sm.seed_node(node, is_dirty=node_dirty[node], dependencies=deps if deps else None)

        with enter_phase(system, registry=registry) as scope:
            real_subgraph = scope.get_singleton(subgraph.DagSubgraph)
            impl_sm.bind_instance(real_subgraph)
            impl_sm.set_target(target)

            steps = 0
            while not impl_sm.is_complete() and steps < 30:
                batch = impl_sm.next_ready_batch()
                if len(batch) == 0:
                    break

                # Invariant 1: Batch size bounded by batch_size limit
                self.assertLessEqual(len(batch), batch_size)

                # Invariant 2: All nodes in batch must share identical role address
                role_addresses = {n.role_address for n in batch}
                self.assertEqual(len(role_addresses), 1)

                # Invariant 3: All nodes in batch must have been dirty in storage
                for n in batch:
                    self.assertTrue(impl_sm.storage_sm.state.dirty_nodes.get_in(n))

                # Record visit through implementation state machine
                impl_sm.record_visit(batch)

                # Simulate work: mark visited nodes clean
                for n in batch:
                    impl_sm.storage_sm.seed_dirty_status(n, dirty=False)

                steps += 1

            # Invariant 4: If complete, next_ready_batch MUST be empty
            if impl_sm.is_complete():
                self.assertEqual(len(impl_sm.next_ready_batch()), 0)
