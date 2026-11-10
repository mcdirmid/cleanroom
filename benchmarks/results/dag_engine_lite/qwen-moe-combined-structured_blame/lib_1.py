# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261109_223953_qwen-moe_dag_engine_lite_combined
# Timestamp: 2026-11-09T22:39:53.000000+00:00
# Benchmark Task: dag_engine_lite
# Model: qwen-moe (Tier 1)
# Methodology: combined
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 2,889,036
#   Cached Inbound Tokens:   34,340,627
#   Outbound Tokens:         596,014
#   Total Tokens:            37,825,677
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     13172.70s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 3, lib: 9, pretense: 17, pretense_coverage: 7, pretense_qa: 18, qa: 6, test: 4 (Total: 64)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       54
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from support.lib.framework import operation
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")


@dataclass
class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class CycleError(DAGError):
    """Error raised when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """

    cycle: Tuple[str, ...]

    def __str__(self) -> str:
        return self.message


@dataclass
class NodeNotFoundError(DAGError):
    """Error raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """

    node_id: str

    def __str__(self) -> str:
        return self.message


@dataclass
class DuplicateNodeError(DAGError):
    """Error raised when attempting to add a node identifier that already exists in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the duplicate node.
    """

    node_id: str

    def __str__(self) -> str:
        return self.message


@dataclass
class NodeExecutionError(DAGError):
    """Raised when an unhandled exception occurs during node action execution.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the failed node.
        cause: Underlying caught exception.
    """

    node_id: str
    cause: Exception

    def __str__(self) -> str:
        return self.message


class NodeState(enum.Enum):
    """Execution lifecycle state of a graph node."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class FailurePolicy(enum.Enum):
    """Policy governing graph execution when a node action fails."""

    FAIL_FAST = "fail_fast"
    CONTINUE_ON_ERROR = "continue_on_error"
    SKIP_DOWNSTREAM = "skip_downstream"


@dataclass(frozen=True)
class NodeDefinition(Generic[T]):
    """Immutable definition of a task node in the directed acyclic graph.

    Args:
        node_id: Unique identifier for the node.
        action: Callable action to execute for this node.
        dependencies: Set of node identifiers that must complete before this node can run.
        priority: Priority value used for wave ordering and tie-breaking (higher runs first).
        retries: Number of retry attempts on failure.
    """

    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    retries: int = 0


@dataclass(frozen=True)
class NodeResult(Generic[T]):
    """Outcome record of a node execution.

    Args:
        node_id: Unique identifier of the node.
        state: Final lifecycle state of the node.
        value: Return value of the action when execution succeeds.
        error: Caught exception when execution fails.
        duration_seconds: Wall-clock elapsed execution time in seconds.
        retries_attempted: Number of retries executed before final state.
    """

    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


@dataclass(frozen=True)
class DAGRunReport:
    """Consolidated summary report of an entire DAG execution run.

    Args:
        total_nodes: Total count of nodes in the graph.
        succeeded_nodes: Identifiers of all nodes that completed successfully.
        failed_nodes: Identifiers of all nodes that failed.
        skipped_nodes: Identifiers of all nodes skipped due to upstream failure.
        cancelled_nodes: Identifiers of all nodes cancelled prior to execution.
        wall_clock_seconds: Total wall-clock time elapsed for the run.
        critical_path: Sequence of node identifiers forming the critical path.
        results: Mapping of node identifier to individual NodeResult outcomes.
    """

    total_nodes: int
    succeeded_nodes: Tuple[str, ...]
    failed_nodes: Tuple[str, ...]
    skipped_nodes: Tuple[str, ...]
    cancelled_nodes: Tuple[str, ...]
    wall_clock_seconds: float
    critical_path: Tuple[str, ...]
    results: Mapping[str, NodeResult[Any]]


class DAG(Singleton[SystemTier], Protocol):
    """Directed Acyclic Graph holding task nodes and directed dependency edges."""

    @operation
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Adds a task node to the graph."""
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        ...

    @operation
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        ...

    @operation
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies)."""
        ...

    @operation
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
        ...

    @operation
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        ...


class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into sequential execution waves."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        ...

    @operation
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node."""
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph."""
        ...


class DAGRunner(Singleton[SystemTier], Protocol):
    """Executes a DAG sequentially to completion under failure policies."""

    @operation
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:49:06Z
# LAST_CHANGED: 2026-11-09T22:49:06Z
# CHANGE: Implemented interface module: dag_engine_lite.py - Fixed exception classes (removed frozen=True per Pyright constraint, added __str__ methods), added @operation decorators to Protocol stubs, cleaned docstrings to remove contract slug references, exported all data types and error classes matching low/dag_engine_lite.pyi specification.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
from __future__ import annotations

import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    get_default_registry,
    get_singleton,
    system,
)
from . import dag_engine_lite


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    """

    tier = system

    def __init__(self) -> None:
        # Private backing state for nodes, upstream deps, and downstream dependents
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    @operation
    @override
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        # Verify node_id is not already present; raise DuplicateNodeError if so
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' already exists in DAG.",
                node_id=node_id,
            )
        # Construct immutable NodeDefinition with frozen dependency set
        dep_set = frozenset(dependencies) if dependencies else frozenset()
        definition = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dep_set,
            priority=priority,
            retries=retries,
        )
        # Insert definition into _nodes
        self._nodes[node_id] = definition
        self._upstream[node_id] = set()
        self._downstream[node_id] = set()
        # Add directed edges from each dependency to node_id (defer existence validation)
        if dependencies:
            for dep_id in dependencies:
                if dep_id not in self._downstream:
                    self._downstream[dep_id] = set()
                self._downstream[dep_id].add(node_id)
                self._upstream[node_id].add(dep_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # Verify presence of both nodes
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{upstream_id}' not found in DAG.",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{downstream_id}' not found in DAG.",
                node_id=downstream_id,
            )
        # Update adjacency sets for directed edge
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # Verify node exists
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        # Remove node from all incident upstream and downstream neighbor sets
        for dep_id in self._upstream[node_id]:
            if node_id in self._downstream.get(dep_id, set()):
                self._downstream[dep_id].discard(node_id)
        for dep_id in self._downstream[node_id]:
            if node_id in self._upstream.get(dep_id, set()):
                self._upstream[dep_id].discard(node_id)
        # Delete node from all dictionaries
        del self._nodes[node_id]
        del self._upstream[node_id]
        del self._downstream[node_id]

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        # Check membership in _nodes
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # Look up node_id; raise NodeNotFoundError if not present
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # Verify node exists
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        # Return a copy of upstream set
        return set(self._upstream[node_id])

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # Verify node exists
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        # Return a copy of downstream set
        return set(self._downstream[node_id])

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        # Return copy of node key set
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # Verify that every dependency in every node definition exists in _nodes
        for node_id, definition in self._nodes.items():
            for dep_id in definition.dependencies:
                if dep_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dep_id}' of node '{node_id}' not found in DAG.",
                        node_id=dep_id,
                    )
        # Depth-first search cycle detection with active recursion path tracking
        self._detect_cycle()

    def _detect_cycle(self) -> None:
        """Run DFS-based cycle detection. Raises CycleError with the cycle sequence if found."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {nid: WHITE for nid in self._nodes}

        def _dfs(node_id: str) -> None:
            color[node_id] = GRAY
            for neighbor in self._upstream.get(node_id, set()):
                if color[neighbor] == GRAY:
                    raise dag_engine_lite.CycleError(
                        message=f"Cycle detected in DAG involving '{neighbor}' and '{node_id}'.",
                        cycle=(neighbor, node_id),
                    )
                if color[neighbor] == WHITE:
                    _dfs(neighbor)
            color[node_id] = BLACK

        for nid in self._nodes:
            if color[nid] == WHITE:
                _dfs(nid)

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # Validate acyclicity before sorting
        self._detect_cycle()
        # Compute in-degree counts from _upstream mapping
        in_degree: Dict[str, int] = {nid: 0 for nid in self._nodes}
        for nid in self._nodes:
            for dep_id in self._upstream.get(nid, set()):
                if dep_id in in_degree:
                    in_degree[nid] += 1
        # Use a sorted approach to maintain priority descending, then node_id ascending order
        # Kahn's algorithm with priority-based tie-breaking
        order: List[str] = []
        # Start with nodes that have in-degree zero, sorted by priority desc then node_id asc
        zero_nodes = sorted(
            [nid for nid, deg in in_degree.items() if deg == 0],
            key=lambda nid: (-self._nodes[nid].priority, nid),
        )
        while zero_nodes:
            # Extract candidate with highest priority
            candidate = zero_nodes.pop(0)
            order.append(candidate)
            # Decrement downstream in-degrees
            for dependent in self._downstream.get(candidate, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        # Insert maintaining sorted order: priority desc, then node_id asc
                        zero_nodes.append(dependent)
                        zero_nodes.sort(key=lambda nid: (-self._nodes[nid].priority, nid))
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        # Collect nodes whose upstream set is empty
        return {nid for nid in self._nodes if not self._upstream.get(nid)}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        # Collect nodes whose downstream set is empty
        return {nid for nid in self._nodes if not self._downstream.get(nid)}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        # Get topological order
        topo_order = self.topological_sort()
        # Resolve duration weights mapping, defaulting to 1.0 for unspecified nodes
        durations: Dict[str, float] = {}
        for nid in self._nodes:
            durations[nid] = estimated_durations.get(nid, 1.0) if estimated_durations else 1.0
        # Compute earliest completion times using dynamic programming
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}
        for nid in topo_order:
            upstream_deps = self._upstream.get(nid, set())
            best_predecessor: Optional[str] = None
            max_completion = 0.0
            for dep in upstream_deps:
                if dep in earliest and earliest[dep] > max_completion:
                    max_completion = earliest[dep]
                    best_predecessor = dep
            earliest[nid] = max_completion + durations[nid]
            predecessor[nid] = best_predecessor
        # Identify terminal node with maximum completion time
        if not earliest:
            return ([], 0.0)
        terminal = max(earliest, key=lambda nid: earliest[nid])
        # Backtrack through predecessors to reconstruct path
        path: List[str] = []
        current: Optional[str] = terminal
        while current is not None:
            path.append(current)
            current = predecessor.get(current)
        path.reverse()
        return (path, earliest[terminal])


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states dictionary mapping node identifiers to dag_engine_lite.NodeState.
    - Synchronizes dynamic node state by discovering registered nodes from _dag.all_nodes().
    """

    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _synchronize_states(self) -> None:
        """Ensure _states contains all nodes from _dag, initializing roots to READY and non-roots to PENDING."""
        all_nodes = self._dag.all_nodes()
        for nid in all_nodes:
            if nid not in self._states:
                # Initialize root nodes (no dependencies) to READY, others to PENDING
                deps = self._dag.get_dependencies(nid)
                # Only mark as READY if all dependencies already exist in _states as SUCCEEDED
                if not deps:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

    @operation
    @override
    def next_wave(self) -> List[str]:
        # Synchronize state with registered nodes
        self._synchronize_states()
        # Gather nodes currently in READY state whose upstream dependencies are all SUCCEEDED
        ready_nodes: List[str] = []
        for nid in self._states:
            if self._states[nid] != dag_engine_lite.NodeState.READY:
                continue
            deps = self._dag.get_dependencies(nid)
            if all(
                self._states.get(dep) == dag_engine_lite.NodeState.SUCCEEDED
                for dep in deps
            ):
                ready_nodes.append(nid)
        # Sort by priority descending, then node_id ascending
        ready_nodes.sort(
            key=lambda nid: (-self._dag.get_node(nid).priority, nid)
        )
        return ready_nodes

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        # Update node state to RUNNING
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        # Update node state to SUCCEEDED
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # Inspect downstream dependents and promote newly unblocked nodes
        dependents = self._dag.get_dependents(node_id)
        for dep_id in dependents:
            deps = self._dag.get_dependencies(dep_id)
            if all(
                self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED
                for d in deps
            ):
                self._states[dep_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        # Synchronize states so all nodes have explicit state entries
        self._synchronize_states()
        # Update node state to FAILED
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        all_nodes = self._dag.all_nodes()
        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Transition all remaining PENDING nodes to CANCELLED
            for nid in all_nodes:
                if self._states.get(nid) in (
                    dag_engine_lite.NodeState.PENDING,
                    dag_engine_lite.NodeState.READY,
                    dag_engine_lite.NodeState.RUNNING,
                ):
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy == dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # Traverse transitive downstream dependents and mark non-terminal as SKIPPED
            self._skip_dependents(node_id)
        elif failure_policy == dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR:
            # Leave unblocked independent nodes eligible; transition blocked dependents to SKIPPED
            for nid in all_nodes:
                if self._states.get(nid) != dag_engine_lite.NodeState.PENDING:
                    continue
                # Check if any dependency is in a failed state
                deps = self._dag.get_dependencies(nid)
                has_failed_dep = any(
                    self._states.get(d) == dag_engine_lite.NodeState.FAILED
                    for d in deps
                )
                if has_failed_dep:
                    self._states[nid] = dag_engine_lite.NodeState.SKIPPED

    def _skip_dependents(self, node_id: str) -> None:
        """Recursively mark transitive downstream dependents as SKIPPED."""
        dependents = self._dag.get_dependents(node_id)
        for dep_id in dependents:
            self._states[dep_id] = dag_engine_lite.NodeState.SKIPPED
            self._skip_dependents(dep_id)

    @operation
    @override
    def is_finished(self) -> bool:
        # Synchronize states with all currently registered nodes
        self._synchronize_states()
        all_nodes = self._dag.all_nodes()
        if not all_nodes:
            # Empty DAG is finished
            return True
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        # Check whether every node is in a terminal state
        for nid in all_nodes:
            if self._states.get(nid) not in terminal_states:
                return False
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        # Verify node_id is registered in _dag
        if not self._dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduled DAG.",
                node_id=node_id,
            )
        # Synchronize states if node_id is absent
        if node_id not in self._states:
            self._synchronize_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        # Ensure states contain all nodes
        self._synchronize_states()
        all_nodes = self._dag.all_nodes()
        # Return shallow copy filtered to only currently registered nodes
        return {nid: self._states[nid] for nid in all_nodes if nid in self._states}


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine_lite.DAG)
      and WaveScheduler service via get_singleton(dag_engine_lite.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, and _results mapping.
    """

    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: WaveScheduler = get_singleton(WaveScheduler)
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        # Validate graph invariants before commencing wave execution
        self._dag.validate()
        # Initialize start wall-clock time and empty results mapping
        start_time = time.monotonic()
        self._results = {}

        # Loop while scheduler reports not finished and waves are available
        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            for node_id in wave:
                definition = self._dag.get_node(node_id)
                # Mark node as RUNNING
                self._scheduler.mark_running(node_id)
                node_start = time.monotonic()
                max_attempts = definition.retries + 1
                success = False
                for attempt in range(max_attempts):
                    try:
                        node_duration = time.monotonic() - node_start
                        value = definition.action()
                        self._results[node_id] = dag_engine_lite.NodeResult(
                            node_id=node_id,
                            state=dag_engine_lite.NodeState.SUCCEEDED,
                            value=value,
                            error=None,
                            duration_seconds=node_duration,
                            retries_attempted=attempt + 1,
                        )
                        self._scheduler.mark_succeeded(node_id)
                        success = True
                        break
                    except Exception as exc:
                        node_duration = time.monotonic() - node_start
                        if attempt == max_attempts - 1:
                            # All retries exhausted, record failure
                            self._results[node_id] = dag_engine_lite.NodeResult(
                                node_id=node_id,
                                state=dag_engine_lite.NodeState.FAILED,
                                value=None,
                                error=exc,
                                duration_seconds=node_duration,
                                retries_attempted=max_attempts,
                            )
                            # Mark failed in scheduler with failure_policy
                            self._scheduler.mark_failed(
                                node_id, failure_policy
                            )
                            success = False
                        # Otherwise: for-loop continues to next attempt (retry)

                if not success:
                    # FAIL_FAST: halt further wave execution
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        return self._build_report(start_time)

        # Build final consolidated report
        return self._build_report(start_time)

    def _build_report(self, start_time: float) -> dag_engine_lite.DAGRunReport:
        """Construct a DAGRunReport from current scheduler states and results."""
        # Populate default NodeResult for any unexecuted terminal nodes from scheduler states
        all_states = self._scheduler.get_all_states()
        for nid, state in all_states.items():
            if nid not in self._results:
                if state in (
                    dag_engine_lite.NodeState.SKIPPED,
                    dag_engine_lite.NodeState.CANCELLED,
                ):
                    self._results[nid] = dag_engine_lite.NodeResult(
                        node_id=nid,
                        state=state,
                        value=None,
                        error=None,
                        duration_seconds=0.0,
                        retries_attempted=0,
                    )
        # Compute critical path
        (critical_path, _) = self._dag.compute_critical_path(None)
        # Compute wall clock time
        wall_clock = time.monotonic() - start_time
        # Gather categorized node tuples
        succeeded = tuple(
            nid for nid, r in self._results.items()
            if r.state == dag_engine_lite.NodeState.SUCCEEDED
        )
        failed = tuple(
            nid for nid, r in self._results.items()
            if r.state == dag_engine_lite.NodeState.FAILED
        )
        skipped = tuple(
            nid for nid, r in self._results.items()
            if r.state == dag_engine_lite.NodeState.SKIPPED
        )
        cancelled = tuple(
            nid for nid, r in self._results.items()
            if r.state == dag_engine_lite.NodeState.CANCELLED
        )
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(critical_path),
            results=self._results,
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DAG,
        keys=[DAG, dag_engine_lite.DAG],
        tier=system,
    )
    reg.register_singleton(
        WaveScheduler,
        keys=[WaveScheduler, dag_engine_lite.WaveScheduler],
        tier=system,
    )
    reg.register_singleton(
        DAGRunner,
        keys=[DAGRunner, dag_engine_lite.DAGRunner],
        tier=system,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-10T01:39:52Z
# LAST_CHANGED: 2026-11-10T01:26:27Z
# CHANGE: Added DuplicateNodeError check in add_node: verifies node_id is not already in _nodes before insertion and raises dag_engine_lite.DuplicateNodeError if present. Also removed duplicate dep_set construction line.
# COVERAGE_AUDIT: 2026-11-10T01:39:52Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-10T01:37:31Z
# PRETENSE_QA_AUDIT: 2026-11-10T01:36:58Z
# QA_AUDIT: 2026-11-10T01:38:43Z
# --- END AUTOFAB METADATA ---
