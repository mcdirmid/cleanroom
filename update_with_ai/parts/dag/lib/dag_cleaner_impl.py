from collections import deque
from typing import Dict, List, Optional, Set
from . import dag_cleaner
from . import dag_config
from . import dag_node_cleaner
from . import dag_storage
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
)


class DagCleaner(dag_cleaner.DagCleaner, Singleton):
    tier = "system"

    def __init__(self) -> None:
        pass

    @property
    def node_visit_limit(self) -> int:
        # Requirement: The node visit limit is obtained from the dag config.
        cfg = get_singleton(dag_config.DagConfig)
        return cfg.node_visit_limit

    def _collect_subgraph(
        self, root: dag_storage.Node, storage: dag_storage.DagStorage
    ) -> Set[dag_storage.Node]:
        # Requirement: Cleaning a target node collects all reachable dependencies from the node.
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
        # Requirement: In each cleaning iteration, reachable nodes are visited in topological order.
        # Requirement: [DagCleaner] Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
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

    def clean(
        self, node: dag_storage.Node, cleaner: dag_node_cleaner.NodeCleaner
    ) -> None:
        # Requirement: Cleaning succeeds when all reachable nodes in the subgraph are clean.
        # Requirement: [DagCleaner] Cleaning concludes when all nodes in the subgraph rooted at the node are clean.
        storage = get_singleton(dag_storage.DagStorage)
        nodes = self._collect_subgraph(node, storage)
        order = self._topological_sort(nodes, storage)

        visits: Dict[dag_storage.Node, int] = {n: 0 for n in nodes}

        while any(storage.is_dirty(n) for n in nodes):
            cleaned_in_pass = False
            for curr in order:
                # Requirement: Visiting a node checks whether the node is dirty, not whether it is cleaned.
                if not storage.is_dirty(curr):
                    continue

                # Requirement: A node is cleaned only if it is dirty and all of its dependencies are clean.
                deps_clean = all(
                    not storage.is_dirty(d.node)
                    for d in storage.get_dependencies(curr)
                    if d.node in nodes
                )
                if not deps_clean:  # pragma: no cover (assumption: acyclic graph ensures dependencies precede dependents)
                    continue

                visits[curr] += 1
                # Requirement: If visiting any node exceeds the node visit limit, the dag cleaner halts with an unexpected failure.
                if visits[curr] > self.node_visit_limit:
                    raise RuntimeError(
                        f"Node {curr.address} exceeded node visit limit of {self.node_visit_limit}"
                    )

                # Requirement: When cleaning a dirty node, the node cleaner is invoked to clean the node.
                # Requirement: [DagCleaner] When cleaning a dirty node using the node cleaner, cleaning delegates to the node cleaner.
                should_continue = cleaner.clean(curr)
                cleaned_in_pass = True
                # Requirement: If the node cleaner communicates that processing cannot continue, cleaning halts.
                # Requirement: [DagCleaner] If the node cleaner communicates that processing cannot continue, cleaning halts.
                if not should_continue:
                    return

            if not cleaned_in_pass and any(
                storage.is_dirty(n) for n in nodes
            ):  # pragma: no cover (assumption: acyclic graph prevents deadlocks)
                # Stalled or circular dirty dependencies
                break


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DagCleaner,
        keys=[DagCleaner, dag_cleaner.DagCleaner],
        tier="system",
    )
