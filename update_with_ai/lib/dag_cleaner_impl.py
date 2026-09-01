"""DAG cleaner implementation executing topological subgraph cleaning."""

from collections import deque
from typing import Set, Dict, List
from .dag_storage import DagStorage, NodeId
from .dag_node_cleaner import NodeCleaner
from .dag_cleaner import DagCleaner


class DagCleanerImpl(DagCleaner):
    def __init__(self, max_iterations: int = 100) -> None:
        self.max_iterations = max_iterations

    def _collect_subgraph(self, root: NodeId, storage: DagStorage) -> Set[NodeId]:
        visited: Set[NodeId] = set()
        queue: deque[NodeId] = deque([root])
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                for dep in storage.get_dependencies(curr):
                    queue.append(dep)
        return visited

    def _topological_sort(self, nodes: Set[NodeId], storage: DagStorage) -> List[NodeId]:
        in_degree: Dict[NodeId, int] = {n: 0 for n in nodes}
        adj: Dict[NodeId, List[NodeId]] = {n: [] for n in nodes}

        for n in nodes:
            for dep in storage.get_dependencies(n):
                if dep in nodes:
                    adj[dep].append(n)
                    in_degree[n] += 1

        queue: deque[NodeId] = deque([n for n, deg in in_degree.items() if deg == 0])
        order: List[NodeId] = []

        while queue:
            curr = queue.popleft()
            order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(nodes):
            raise RuntimeError(f"Cycle detected in subgraph containing {nodes}")

        return order

    def clean_subgraph(
        self,
        root: NodeId,
        storage: DagStorage,
        cleaner: NodeCleaner,
    ) -> None:
        nodes = self._collect_subgraph(root, storage)
        order = self._topological_sort(nodes, storage)

        iterations = 0
        while True:
            iterations += 1
            if iterations > self.max_iterations:
                raise RuntimeError(f"Cleaning pass exceeded execution limit of {self.max_iterations} iterations")

            cleaned_any = False
            for node in order:
                if storage.is_dirty(node):
                    pending = storage.get_pending_messages(node)
                    # Clear pending messages before routing new messages from outcome
                    storage.clear_pending_messages(node)
                    outcome = cleaner.clean_node(node, pending)
                    if outcome is not None:
                        for item in outcome:
                            content_str = getattr(item, "content", str(item))
                            # Feedback messages (e.g. Blamed ...) route upstream to dependencies
                            if content_str.startswith("Blamed "):
                                deps = storage.get_dependencies(node)
                                for dep in deps:
                                    storage.queue_pending_messages(dep, [item])
                                    storage.mark_dirty(dep)
                            else:
                                rdeps = storage.get_reverse_dependencies(node)
                                for rdep in rdeps:
                                    storage.queue_pending_messages(rdep, [item])
                                    storage.mark_dirty(rdep)
                        cleaned_any = True
                    else:
                        storage.mark_dirty(node)
                        return

            if not cleaned_any or not any(storage.is_dirty(n) for n in nodes):
                break
