"""
Implementation LLS: dag_impl
Provides concrete implementation of DAG cleaning orchestration.
"""

import os
import signal
import threading
from typing import List, Set, cast
from dataclasses import dataclass
from collections import deque

from .dag_storage import NodeId, NodeMessage, PendingMessages, DagStorage
from .dag_clean_logic import (
    CleanResult,
    DagCleanLogic,
    ChangeResult,
    FeedbackResult,
    NoChangeResult,
    FailureResult,
)
from .dag import Dag, CleaningResult

# SIGTERM handler: bazel's process-wrapper sends SIGTERM when --test_timeout
# expires (then SIGKILL after a grace period). We must terminate immediately.
#
# os._exit() is required here instead of sys.exit(): sys.exit() raises
# SystemExit, which unittest's bare `except:` in _Outcome.testPartExecutor
# swallows as a plain test error. The test suite then keeps running (any
# remaining infinite loops keep spinning) and only dies when the timeout
# mechanism escalates to SIGKILL -- or never, if it only sends SIGTERM, which
# leaves a lingering process (and a zombie when the parent dies without
# reaping it). os._exit() cannot be intercepted, so the process dies the
# moment SIGTERM arrives and the parent can reap it.
def _sigterm_handler(signum, frame):
    os._exit(1)

# Register only from the main thread; signal.signal() raises ValueError if
# called from a worker thread (e.g. when this module is imported lazily).
if threading.current_thread() is threading.main_thread():
    signal.signal(signal.SIGTERM, _sigterm_handler)


@dataclass
class Config:
    """
    Configuration for the dag_impl implementation.

    HLS Justification: The dag_impl implementation is configured with dag_storage
    (message persistence and graph access) and dag_clean_logic (message processing
    and dirtiness determination).
    """
    storage: DagStorage
    clean_logic: DagCleanLogic


class DagImpl(Dag):
    """
    Implementation of DAG cleaning orchestration.
    
    Responsibilities:
    - Traverses graph from target_node following dependencies to identify subgraph.
    - Computes topological sort once (dependencies before dependents).
    - Iteratively: finds earliest dirty node in sort order, ensures no dependencies are dirty, 
      cleans it.
    - For each dirty node: reads pending messages -> invokes clean_logic.clean -> on success, 
      deletes old messages and routes new ones (change to reverse deps, feedback to specified deps) 
      -> on failure, halts immediately.
    - All reads/writes go through dag_storage; no caching.
    
    HLS Justification: "Provides the dag_impl implementation that fulfills the dag interface. 
    Uses the configured dag_storage for message persistence and dag_clean_logic for processing 
    node messages."
    """
    
    def __init__(self, config: Config):
        """
        Initialize DAG implementation with configuration.
        
        Invariants:
        - No caching; all state reads/writes go through dag_storage.
        - On failure, processing halts immediately; no recovery or retry.
        """
        self.storage = config.storage
        self.clean_logic = config.clean_logic
    
    def _get_subgraph_nodes(self, target_node: NodeId) -> Set[NodeId]:
        """
        Traverse from target_node following dependencies through dag_storage
        to identify the subgraph (the target node and its transitive dependencies).
        """
        subgraph = set()
        stack = [target_node]
        while stack:
            node = stack.pop()
            if node not in subgraph:
                subgraph.add(node)
                # Add dependencies (going backwards from target)
                for dep in self.storage.get_node_dependencies(node):
                    if dep not in subgraph:
                        stack.append(dep)
        return subgraph
    
    def _topological_sort(self, nodes: Set[NodeId]) -> List[NodeId]:
        """
        Compute topological sort (dependencies before dependents).

        Raises ValueError if the graph contains a cycle (cycle members would
        otherwise be silently dropped from the order, causing dirty nodes to be
        skipped forever).
        """
        # Build adjacency for the subgraph from dag_storage
        adjacency = {node: [] for node in nodes}
        in_degree = {node: 0 for node in nodes}
        
        for node in nodes:
            for dep in self.storage.get_node_dependencies(node):
                if dep in nodes:
                    adjacency[dep].append(node)
                    in_degree[node] += 1
        
        # Kahn's algorithm. The initial queue sorts the in-degree-0 nodes so
        # the ordering is deterministic (nodes is a set; iteration order would
        # otherwise vary across runs).
        result = []
        queue = deque(sorted(node for node in nodes if in_degree[node] == 0))
        
        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(result) != len(nodes):
            raise ValueError(
                "Graph contains a cycle; topological sort incomplete "
                f"({len(result)}/{len(nodes)} nodes ordered)"
            )
        
        return result
    
    def _get_dependencies(self, node_id: NodeId) -> List[NodeId]:
        """Get dependencies of a node through dag_storage."""
        return self.storage.get_node_dependencies(node_id)
    
    def _is_dirty(self, node_id: NodeId) -> bool:
        """Check if a node is dirty using clean_logic."""
        messages = self.storage.get_pending_messages(node_id)
        return self.clean_logic.is_dirty(node_id, messages)
    
    def _has_dirty_dependencies(self, node_id: NodeId) -> bool:
        """Check if any dependency of node is dirty."""
        for dep in self._get_dependencies(node_id):
            if self._is_dirty(dep):
                return True
        return False
    
    def _route_messages(self, node_id: NodeId, result: CleanResult) -> None:
        """
        Route messages based on clean result.
        - ChangeResult: broadcast to all reverse dependencies
        - FeedbackResult: deliver to specified dependencies
        - NoChangeResult: no messages to route
        - FailureResult: no messages to route
        """
        if isinstance(result, ChangeResult):
            # Broadcast to all known reverse dependencies (as provided by
            # dag_storage). A known reverse dependency that is not in the
            # current graph (its node data cannot be resolved) is skipped.
            broadcast = cast(List[NodeMessage], result.messages)
            for target in self.storage.get_known_reverse_dependencies(node_id):
                try:
                    self.storage.add_messages(target, broadcast)
                except ValueError:
                    continue

        elif isinstance(result, FeedbackResult):
            # Deliver to specified dependencies
            for target, message in result.messages:
                self.storage.add_messages(target, [message])

        # NoChangeResult and FailureResult have no messages to route

    def clean_subgraph(self, target_node: NodeId) -> CleaningResult:
        """
        Clean all dirty nodes in the subgraph rooted at target_node until none remain.
        
        On failure: failed node's messages remain unchanged; previously cleaned nodes 
        retain changes; processing halts.
        
        Termination: cleaning is bounded by a cap on total cleans
        (len(nodes) * (len(nodes) + 1)). Without a bound, a clean result that
        re-routes messages back into the subgraph (e.g. feedback to an upstream
        node or to the node itself) or an is_dirty() that never clears would make
        the loop run forever. Exceeding the cap returns a failure result instead
        of looping indefinitely.
        """
        # Get subgraph nodes
        subgraph_nodes = self._get_subgraph_nodes(target_node)

        # Compute topological sort once; a cycle returns a failure result with
        # state unchanged (no messages deleted or routed).
        try:
            sorted_nodes = self._topological_sort(subgraph_nodes)
        except ValueError:
            return (False, FailureResult())

        # Termination cap: each clean can re-dirty nodes via change/feedback
        # messages, so allow a bounded number of cleans and fail loudly rather
        # than loop forever on a message cycle.
        max_cleans = len(sorted_nodes) * (len(sorted_nodes) + 1)
        total_cleans = 0

        # Iterative cleaning.
        #
        # The loop must be bounded by max_cleans, not just by progress: a clean
        # result that re-routes messages back into the subgraph (feedback to an
        # upstream node or to the node itself) or an is_dirty() that never
        # clears keeps making "progress" forever. The cap is part of the loop
        # condition so we can exit and report the failure instead of spinning.
        progress_made = True
        last_result: CleanResult = NoChangeResult()
        while progress_made and total_cleans < max_cleans:
            progress_made = False

            for node in sorted_nodes:
                # Check if node is dirty
                if not self._is_dirty(node):
                    continue

                # Ensure no dependencies are dirty
                if self._has_dirty_dependencies(node):
                    continue

                # Clean the node
                progress_made = True
                messages = self.storage.get_pending_messages(node)
                result = self.clean_logic.clean(node, messages)
                total_cleans += 1

                if isinstance(result, FailureResult):
                    # Failure: halt immediately, failed node's messages remain unchanged
                    return (False, FailureResult())

                print(f"{node} cleaned")

                # Feedback targets must stay within the subgraph; routing
                # elsewhere would leave messages that this clean never processes.
                if isinstance(result, FeedbackResult):
                    for target, _ in result.messages:
                        if target not in subgraph_nodes:
                            return (False, FailureResult())

                # Success: route new messages (reads the node's known reverse
                # dependencies), then delete the node's data.
                self._route_messages(node, result)
                self.storage.delete_node_data(node)
                last_result = result

        # Cap reached: a message cycle or a non-clearing dirty state prevented
        # termination. If the cap was reached exactly as the final dirty node
        # was cleaned (no dirty nodes remain), the run completed within the
        # bound and succeeds.
        if total_cleans >= max_cleans:
            if any(self._is_dirty(n) for n in sorted_nodes):
                return (False, FailureResult())

        return (True, last_result)