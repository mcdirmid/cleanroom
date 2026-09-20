# Requirements specified in dag_subgraph_impl.pyi
from collections import deque
from typing import Dict, List, Optional, Sequence, Set
from . import dag_config
from . import dag_storage
from . import dag_subgraph
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)


class DagSubgraph(dag_subgraph.DagSubgraph, Singleton):
    tier = system

    def __init__(self) -> None:
        self._root: Optional[dag_storage.Node] = None
        self._nodes: Set[dag_storage.Node] = set()
        self._order: List[dag_storage.Node] = []
        self._visits: Dict[dag_storage.Node, int] = {}

    def _collect_subgraph(
        self, root: dag_storage.Node, storage: dag_storage.DagStorage
    ) -> Set[dag_storage.Node]:
        visited: Set[dag_storage.Node] = set()
        queue: deque[dag_storage.Node] = deque([root])
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                for dep in storage.get_dependencies(curr):
                    queue.append(dep.node)
        return visited

    def _topological_sort(
        self, nodes: Set[dag_storage.Node], storage: dag_storage.DagStorage
    ) -> List[dag_storage.Node]:
        in_degree: Dict[dag_storage.Node, int] = {n: 0 for n in nodes}
        adj: Dict[dag_storage.Node, List[dag_storage.Node]] = {n: [] for n in nodes}

        for n in nodes:
            for dep in storage.get_dependencies(n):
                if dep.node in nodes:
                    adj[dep.node].append(n)
                    in_degree[n] += 1

        queue: deque[dag_storage.Node] = deque(
            [n for n, deg in in_degree.items() if deg == 0]
        )
        order: List[dag_storage.Node] = []

        while queue:
            curr = queue.popleft()
            order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    def set_target(self, root: dag_storage.Node) -> None:
        # Requirement: [DagSubgraph] Setting a target collects all reachable dependency nodes from the target node in dag storage and computes their dependency-first topological order.
        # Requirement: Setting a target node scopes the target subgraph to all reachable dependency nodes rooted at the target node in dag storage, arranged in dependency-first topological order.
        storage = get_singleton(dag_storage.DagStorage)
        self._root = root
        self._nodes = self._collect_subgraph(root, storage)
        self._order = self._topological_sort(self._nodes, storage)
        self._visits = {n: 0 for n in self._nodes}

    @property
    def is_complete(self) -> bool:
        # Requirement: [DagSubgraph] The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage.
        storage = get_singleton(dag_storage.DagStorage)
        return not any(storage.is_dirty(n) for n in self._nodes)

    def next_ready_batch(self) -> List[dag_storage.Node]:
        storage = get_singleton(dag_storage.DagStorage)
        cfg = get_singleton(dag_config.DagConfig)
        batch_size = max(1, cfg.batch_size)

        for i, curr in enumerate(self._order):
            if not storage.is_dirty(curr):
                continue

            deps_clean = all(
                not storage.is_dirty(d.node)
                for d in storage.get_dependencies(curr)
                if d.node in self._nodes
            )
            if not deps_clean:
                continue

            # Requirement: [DagSubgraph] When obtaining the next ready batch, uncleaned dirty nodes in topological order whose dependencies in the target subgraph are clean in dag storage are selected, grouped by role address up to a maximum batch size.
            # Requirement: The next ready batch consists of contiguous dirty nodes in topological order that share the same role address and have all their dependencies in the target subgraph clean in dag storage, starting from the earliest ready dirty node and bounded by the batch size obtained from dag config.
            batch: List[dag_storage.Node] = [curr]
            batch_set: Set[dag_storage.Node] = {curr}

            if batch_size > 1:
                for cand in self._order[i + 1 :]:
                    if len(batch) >= batch_size:
                        break
                    if not storage.is_dirty(cand):
                        continue
                    if cand.role_address != curr.role_address:
                        continue
                    cand_deps_clean = all(
                        d.node in batch_set or not storage.is_dirty(d.node)
                        for d in storage.get_dependencies(cand)
                        if d.node in self._nodes
                    )
                    if cand_deps_clean:
                        batch.append(cand)
                        batch_set.add(cand)

            return batch

        # Requirement: If no dirty node in the target subgraph has all its dependencies in the target subgraph clean in dag storage, the next ready batch is an empty sequence.
        return []

    def record_visit(self, nodes: Sequence[dag_storage.Node]) -> None:
        cfg = get_singleton(dag_config.DagConfig)
        limit = cfg.node_visit_limit

        for node in nodes:
            # Requirement: [DagSubgraph] Recording a visit increments the visit count for each node in the batch and raises an unexpected failure if visiting any node exceeds the node visit limit.
            # Requirement: Recording a visit for a batch of nodes advances the visit count for each node in the batch, raising an unexpected failure if any node exceeds the node visit limit obtained from dag config.
            count = self._visits.get(node, 0) + 1
            self._visits[node] = count
            if count > limit:
                raise RuntimeError(
                    f"Node ({node.unit_address}, {node.role_address}) exceeded node visit limit of {limit}"
                )


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DagSubgraph,
        keys=[DagSubgraph, dag_subgraph.DagSubgraph],
        tier=system,
    )
