# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T04:59:23Z
# CHANGE: Order ready nodes by role tier depth then unit address then role address, end each ready batch before the first node with unsatisfied in-subgraph dependencies, and bound batches at exactly the configured batch size
# CODE_HASH: a5f668e73384
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
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
from . import subgraph
from .dag_storage import DagNode, DagStorage

# Requirements specified in subgraph_impl.pyi


class DagSubgraph(subgraph.DagSubgraph, InTier[SystemTier], Singleton):
    """Coordinates topological subgraph queries and visit bounds across graph storage."""

    tier = system

    def __init__(self) -> None:
        self._topological_order: List[DagNode] = []
        self._visit_counts: Dict[DagNode, int] = {}

    @staticmethod
    def _role_name(role_address: str) -> str:
        # Contract: Reduces a fully qualified role address to its bare role name for precedence comparison.
        """Reduces a fully qualified role address to its bare role name."""
        return role_address.split(":")[-1].strip().lower()

    @staticmethod
    def _role_depths(role_dependencies: Dict[str, Set[str]]) -> Dict[str, int]:
        # Contract: MUST dynamically prioritize upstream roles before downstream roles based on role dependency depth.
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
        # Contract: MUST collect reachable dependency nodes from the target node in graph storage.
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
        # Contract: Identifies dependencies of a node that belong to the active target subgraph.
        """The dependencies of a node that lie inside the active target subgraph."""
        return [
            dependency.node
            for dependency in storage.get_dependencies(node)
            if dependency.node in subgraph
        ]

    def set_target(self, target: DagNode) -> None:
        """Sets the active execution subgraph target node."""
        storage = get_singleton(DagStorage)
        # Contract: MUST collect reachable dependency nodes from the target node in graph storage.
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

        # Contract: MUST dynamically prioritize upstream roles before downstream roles based on role dependency depth.
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

        # Contract: MUST compute the dependency-first topological order of reachable dependency nodes.
        ready: List[DagNode] = [node for node in reachable if not blocking[node]]
        order: List[DagNode] = []
        while ready:
            # Contract: MUST break topological sorting ties by role tier depth first, unit address second, unqualified role name third.
            ready.sort(
                key=lambda node: (
                    depths.get(self._role_name(str(node.role_address)), 0),
                    str(node.unit_address),
                    self._role_name(str(node.role_address)),
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
        # Contract: MUST return true if, but only if, all reachable nodes in the target subgraph are clean in graph storage.
        storage = get_singleton(DagStorage)
        return not any(storage.is_dirty(node) for node in self._topological_order)

    def next_ready_batch(self) -> Sequence[DagNode]:
        """Provides the next ready batch of dirty nodes to clean."""
        storage = get_singleton(DagStorage)
        config = get_singleton(dag_config.DagConfig)
        # Contract: MUST bound batch size to the limit obtained from configuration.
        batch_limit = int(config.batch_size)
        subgraph = set(self._topological_order)

        # Contract: MUST start from the earliest ready dirty node in topological order whose dependencies are clean.
        start_index: Optional[int] = None
        for index, node in enumerate(self._topological_order):
            if not storage.is_dirty(node):
                continue
            dependencies = self._subgraph_dependencies(node, storage, subgraph)
            if all(not storage.is_dirty(dependency) for dependency in dependencies):
                start_index = index
                break

        # Contract: WHEN no dirty node in target subgraph has all of its dependencies clean, MUST return an empty sequence.
        if start_index is None:
            return []

        # Contract: MUST ensure selected dirty nodes share the same role address.
        role_address = self._topological_order[start_index].role_address
        batch: List[DagNode] = []
        collected: Set[DagNode] = set()

        # Contract: MUST select dirty nodes that are contiguous in topological order.
        for index in range(start_index, len(self._topological_order)):
            if len(batch) >= batch_limit:
                break
            node = self._topological_order[index]
            if not storage.is_dirty(node):
                break
            if node.role_address != role_address:
                break
            dependencies = self._subgraph_dependencies(node, storage, subgraph)
            # Contract: WHEN a node's dependencies are neither clean nor already collected in same batch, MUST end batch before that node.
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
            # Contract: MUST advance the visit count for each node in the batch.
            visits = self._visit_counts.get(node, 0) + 1
            self._visit_counts[node] = visits
            # Contract: WHEN any node in the batch exceeds node visit limit, MUST raise an unexpected failure (RuntimeError).
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
        keys=[DagSubgraph, subgraph.DagSubgraph, InTier[SystemTier]],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
