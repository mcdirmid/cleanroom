"""
Implementation of the dag_cleaner interface (DagCleaner).

Implements the DagCleaner Protocol's clean_subgraph operation, using
DagStorage for message persistence and graph access, and DagCleanLogic
for message processing and dirtiness determination.
"""

from __future__ import annotations

from .dag_storage import DagStorage, NodeId, NodeMessage, PendingMessages
from .dag_clean_logic import DagCleanLogic, CleanResult, ChangeResult, FeedbackResult, NoChangeResult, FailureResult
from .dag_cleaner import DagCleaner, CleaningResult


class DagCleanerImpl(DagCleaner):
    """Fulfills the DagCleaner contract per its LLS."""

    def __init__(self, storage: DagStorage, clean_logic: DagCleanLogic) -> None:
        """Construct with dag_storage and dag_clean_logic."""
        self.storage = storage
        self.clean_logic = clean_logic

    def clean_subgraph(self, target_node: NodeId) -> CleaningResult:
        """
        Clean all dirty nodes in the subgraph rooted at target_node.

        Returns (True, CleanResult) on success or (False, FailureResult) on failure.
        Traverses the subgraph in topological order, validates feedback targets,
        detects cycles, and applies cleaning with bounds on total invocations.
        """
        # Build the subgraph: target_node and all reachable dependencies
        subgraph = self._build_subgraph(target_node)
        if subgraph is None:
            # Cycle detected
            return (False, FailureResult(type="failure"))

        subgraph_set = set(subgraph)
        bound = len(subgraph) * (len(subgraph) + 1)
        clean_count = 0

        # Process nodes until all are clean or bound exceeded.
        # Track which nodes need re-cleaning (became dirty during processing).
        dirty_nodes: set[NodeId] = {
            nid for nid in subgraph
            if self.clean_logic.is_dirty(nid, self.storage.get_pending_messages(nid))
        }

        while dirty_nodes:
            made_progress = False
            for node_id in subgraph:
                if clean_count > bound:
                    return (False, FailureResult(type="failure"))

                if node_id not in dirty_nodes:
                    continue

                pending = self.storage.get_pending_messages(node_id)

                if not self.clean_logic.is_dirty(node_id, pending):
                    dirty_nodes.discard(node_id)
                    continue

                result = self.clean_logic.clean(node_id, pending)
                clean_count += 1
                made_progress = True

                if clean_count > bound:
                    return (False, FailureResult(type="failure"))

                if isinstance(result, FailureResult):
                    return (False, FailureResult(type="failure"))

                if isinstance(result, ChangeResult):
                    # Route change messages to all known reverse dependencies
                    # (skipping any known reverse dependency not in the graph)
                    rev_deps = self.storage.get_known_reverse_dependencies(node_id)
                    for rev_dep in rev_deps:
                        try:
                            self.storage.add_messages(rev_dep, result.messages)
                        except (KeyError, ValueError):
                            pass  # reverse dep not in graph, skip
                    # Delete node data (pending messages + known reverse dependencies)
                    self.storage.delete_node_data(node_id)
                    dirty_nodes.discard(node_id)

                elif isinstance(result, FeedbackResult):
                    # Validate each feedback target is within the subgraph
                    for target_node_id, message in result.messages:
                        if target_node_id not in subgraph_set:
                            return (False, FailureResult(type="failure"))
                        self.storage.add_messages(target_node_id, [message])
                        dirty_nodes.add(target_node_id)
                    # FeedbackResult: keep pending messages and known reverse dependencies

                elif isinstance(result, NoChangeResult):
                    # Clear pending messages; known reverse dependencies remain
                    self.storage.clear_pending_messages(node_id)
                    dirty_nodes.discard(node_id)

            if not made_progress:
                # No dirty nodes remain but dirty_nodes is non-empty
                # This can happen if nodes are still marked dirty but
                # is_dirty returns False for them now
                dirty_nodes.clear()

        return (True, NoChangeResult(type="no_change"))

    def _build_subgraph(self, target_node: NodeId) -> list[NodeId] | None:
        """
        Build the subgraph rooted at target_node in topological order.

        Returns None if a cycle is detected.
        Uses iterative DFS-based topological sort with cycle detection.
        """
        # Collect all nodes in the subgraph via iterative DFS
        visited: set[NodeId] = set()
        stack: list[NodeId] = [target_node]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            deps = self.storage.get_node_dependencies(node)
            for dep in deps:
                if dep not in visited:
                    stack.append(dep)

        # Topological sort via iterative DFS with coloring
        # WHITE=0 (unvisited), GRAY=1 (in progress), BLACK=2 (done)
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[NodeId, int] = {node: WHITE for node in visited}
        topo_order: list[NodeId] = []

        for start_node in visited:
            if color[start_node] != WHITE:
                continue
            # Iterative DFS using explicit stack
            # Each stack entry is (node, iter_over_deps)
            dep_iter = iter(self.storage.get_node_dependencies(start_node))
            call_stack: list[tuple[NodeId, object]] = [(start_node, dep_iter)]
            color[start_node] = GRAY

            while call_stack:
                node, dep_iter = call_stack[-1]
                try:
                    dep = next(dep_iter)
                except StopIteration:
                    # All dependencies processed
                    call_stack.pop()
                    color[node] = BLACK
                    topo_order.append(node)
                    continue

                if dep not in color:
                    continue  # dep not in subgraph
                if color[dep] == GRAY:
                    return None  # cycle detected
                if color[dep] == WHITE:
                    color[dep] = GRAY
                    call_stack.append((dep, iter(self.storage.get_node_dependencies(dep))))

        # topo_order is in reverse topological order (leaves first),
        # so reverse it to get dependencies before dependents
        topo_order.reverse()
        return topo_order
