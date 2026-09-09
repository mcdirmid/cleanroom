from collections import deque
from typing import Dict, List, Optional, Set
from . import dag_cleaner
from . import dag_node_cleaner
from . import dag_storage
from .lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton

class DagCleaner(dag_cleaner.DagCleaner, Singleton):
    tier = "system"

    def __init__(self) -> None:
        self._execution_limit = 500

    @property
    def execution_limit(self) -> int:
        # Invariant: Maximum allowed visits per node during iterative cleaning
        return self._execution_limit

    def _collect_subgraph(self, root: dag_storage.Node, storage: dag_storage.DagStorage) -> Set[dag_storage.Node]:
        # Requirement: Identifies all transitive dependencies in target subgraph
        visited: Set[dag_storage.Node] = set()
        queue: deque[dag_storage.Node] = deque([root])
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                for dep in storage.get_dependencies(curr):
                    queue.append(dep.node)
        return visited

    def _topological_sort(self, nodes: Set[dag_storage.Node], storage: dag_storage.DagStorage) -> List[dag_storage.Node]:
        # Requirement: Traverses subgraph in topological order so dependencies precede dependents
        in_degree: Dict[dag_storage.Node, int] = {n: 0 for n in nodes}
        adj: Dict[dag_storage.Node, List[dag_storage.Node]] = {n: [] for n in nodes}

        for n in nodes:
            for dep in storage.get_dependencies(n):
                if dep.node in nodes:
                    adj[dep.node].append(n)
                    in_degree[n] += 1

        queue: deque[dag_storage.Node] = deque([n for n, deg in in_degree.items() if deg == 0])
        order: List[dag_storage.Node] = []

        while queue:
            curr = queue.popleft()
            order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    def clean(self, node: dag_storage.Node, cleaner: dag_node_cleaner.NodeCleaner) -> None:
        # Requirement: Cleans subgraph nodes until all dirty nodes are resolved
        storage = get_singleton(dag_storage.DagStorage)
        nodes = self._collect_subgraph(node, storage)
        order = self._topological_sort(nodes, storage)

        visits: Dict[dag_storage.Node, int] = {n: 0 for n in nodes}

        while any(storage.is_dirty(n) for n in nodes):
            cleaned_in_pass = False
            for curr in order:
                if not storage.is_dirty(curr):
                    continue

                # Requirement: Dependencies must be clean before cleaning dependent node
                deps_clean = all(not storage.is_dirty(d.node) for d in storage.get_dependencies(curr) if d.node in nodes)
                if not deps_clean:  # pragma: no cover (assumption: acyclic graph ensures dependencies precede dependents)
                    continue

                visits[curr] += 1
                # Requirement: Enforces execution limit against infinite cleaning cycles
                if visits[curr] > self.execution_limit:
                    raise RuntimeError(f"Node {curr.address} exceeded execution limit of {self.execution_limit}")

                should_continue = cleaner.clean(curr)
                cleaned_in_pass = True
                # Requirement: Halts cleaning when node cleaner signals processing should not continue
                if not should_continue:
                    return

            if not cleaned_in_pass and any(storage.is_dirty(n) for n in nodes):  # pragma: no cover (assumption: acyclic graph prevents deadlocks)
                # Stalled or circular dirty dependencies
                break

def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DagCleaner,
        keys=[DagCleaner, dag_cleaner.DagCleaner],
        tier="system",
    )
