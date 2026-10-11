# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-11T22:09:03Z
# LAST_CHANGED: 2026-10-11T04:59:23Z
# CHANGE: Order ready nodes by role tier depth then unit address then role address, end each ready batch before the first node with unsatisfied in-subgraph dependencies, and bound batches at exactly the configured batch size
# CODE_HASH: a5f668e73384
# COVERAGE_AUDIT: 2026-10-11T22:09:03Z
# QA_AUDIT: 2026-10-11T22:09:03Z
# --- END CLEANROOM METADATA ---

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set

from support.lib.lifecycle import (
    InTier,
    LifecycleRegistry,
    Singleton,
    SystemTier,
    get_default_registry,
    get_singleton,
    system,
)

from . import dag_config
from . import dag_subgraph
from .dag_storage import DagNode, DagStorage

# Requirements specified in dag_subgraph_impl.pyi


class DagSubgraph(dag_subgraph.DagSubgraph, InTier[SystemTier], Singleton):
    """Coordinates topological subgraph queries and visit bounds across graph storage."""

    tier = system

    def __init__(self) -> None:
        self._target: Optional[DagNode] = None
        self._topological_order: List[DagNode] = []
        self._visit_counts: Dict[DagNode, int] = {}

    @staticmethod
    def _role_name(role_address: str) -> str:
        """Reduces a fully qualified role address to its bare role name."""
        return role_address.split(":")[-1].strip().lower()

    @staticmethod
    def _role_depths(role_dependencies: Dict[str, Set[str]]) -> Dict[str, int]:
        """Ranks roles by dependency depth so that upstream roles precede downstream roles."""
        depths: Dict[str, int] = {}
        resolving: Set[str] = set()

        def _depth(role: str) -> int:
            if role in depths:
                return depths[role]
            if role in resolving:
                return 0
            resolving.add(role)
            upstream = role_dependencies.get(role, set())
            if upstream:
                value = 1 + max(_depth(dependency) for dependency in upstream)
            else:
                value = 0
            resolving.discard(role)
            depths[role] = value
            return value

        for role in role_dependencies:
            _depth(role)
        return depths

    def _collect_reachable(self, target: DagNode, storage: DagStorage) -> Set[DagNode]:
        """Walks upstream dependencies from the target node into a complete reachable set."""
        reachable: Set[DagNode] = {target}
        pending: List[DagNode] = [target]
        while pending:
            current = pending.pop(0)
            for dependency in storage.get_dependencies(current):
                if dependency.node not in reachable:
                    reachable.add(dependency.node)
                    pending.append(dependency.node)
        return reachable

    def _subgraph_dependencies(
        self, node: DagNode, storage: DagStorage, subgraph: Set[DagNode]
    ) -> List[DagNode]:
        """The dependencies of a node that lie inside the active target subgraph."""
        return [
            dependency.node
            for dependency in storage.get_dependencies(node)
            if dependency.node in subgraph
        ]

    def set_target(self, target: DagNode) -> None:
        """Sets the active execution subgraph target node."""
        self._target = target
        storage = get_singleton(DagStorage)
        reachable = self._collect_reachable(target, storage)

        role_dependencies: Dict[str, Set[str]] = {
            self._role_name(str(node.role_address)): set() for node in reachable
        }
        for node in reachable:
            role = self._role_name(str(node.role_address))
            for dependency in storage.get_dependencies(node):
                dependency_role = self._role_name(str(dependency.node.role_address))
                if dependency_role != role:
                    role_dependencies[role].add(dependency_role)

        depths = self._role_depths(role_dependencies)

        blocking: Dict[DagNode, Set[DagNode]] = {}
        dependents: Dict[DagNode, Set[DagNode]] = {node: set() for node in reachable}
        for node in reachable:
            node_dependencies = set(
                self._subgraph_dependencies(node, storage, reachable)
            )
            blocking[node] = node_dependencies
            for dependency_node in node_dependencies:
                dependents[dependency_node].add(node)

        ready: List[DagNode] = [node for node in reachable if not blocking[node]]
        order: List[DagNode] = []
        while ready:
            ready.sort(
                key=lambda node: (
                    depths.get(self._role_name(str(node.role_address)), 0),
                    str(node.unit_address),
                    str(node.role_address),
                )
            )
            chosen = ready.pop(0)
            order.append(chosen)
            for dependent in list(dependents[chosen]):
                blocking[dependent].discard(chosen)
                if not blocking[dependent]:
                    ready.append(dependent)

        self._topological_order = order

    def is_complete(self) -> bool:
        """Reports whether every reachable node in the target subgraph is clean."""
        storage = get_singleton(DagStorage)
        return not any(storage.is_dirty(node) for node in self._topological_order)

    def next_ready_batch(self) -> Sequence[DagNode]:
        """Provides the next ready batch of dirty nodes to clean."""
        storage = get_singleton(DagStorage)
        config = get_singleton(dag_config.DagConfig)
        batch_limit = int(config.batch_size)
        subgraph = set(self._topological_order)

        start_index: Optional[int] = None
        for index, node in enumerate(self._topological_order):
            if not storage.is_dirty(node):
                continue
            dependencies = self._subgraph_dependencies(node, storage, subgraph)
            if all(not storage.is_dirty(dependency) for dependency in dependencies):
                start_index = index
                break

        if start_index is None:
            return []

        role_address = self._topological_order[start_index].role_address
        batch: List[DagNode] = []
        collected: Set[DagNode] = set()

        for index in range(start_index, len(self._topological_order)):
            if len(batch) >= batch_limit:
                break
            node = self._topological_order[index]
            if not storage.is_dirty(node):
                break
            if node.role_address != role_address:
                break
            dependencies = self._subgraph_dependencies(node, storage, subgraph)
            if not all(
                not storage.is_dirty(dependency) or dependency in collected
                for dependency in dependencies
            ):
                break
            batch.append(node)
            collected.add(node)

        return batch

    def record_visit(self, batch: Sequence[DagNode]) -> None:
        """Records a visit for a batch of nodes being cleaned."""
        config = get_singleton(dag_config.DagConfig)
        visit_limit = int(config.node_visit_limit)
        for node in batch:
            visits = self._visit_counts.get(node, 0) + 1
            self._visit_counts[node] = visits
            if visits > visit_limit:
                raise RuntimeError(
                    f"Node visit limit exceeded ({visit_limit}) for node '{node.unit_address}:{node.role_address}'"
                )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DagSubgraph,
        keys=[DagSubgraph, dag_subgraph.DagSubgraph, InTier[SystemTier]],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
