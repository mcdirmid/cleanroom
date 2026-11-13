# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261113_213435_gemini-carbon_dag_engine_lite_pretense
# Timestamp: 2026-11-13T21:34:35.789564+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-carbon (Tier 4)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 2,021,411
#   Cached Inbound Tokens:   26,714,826
#   Outbound Tokens:         188,790
#   Total Tokens:            28,925,027
#   Financial Cost ($USD):   $8.6022
#   Wall Clock Duration:     3304.79s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 7, pretense: 5, pretense_coverage: 4, pretense_qa: 11 (Total: 27)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       2
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface definitions and domain types for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import (
    Any,
    Callable,
    Collection,
    FrozenSet,
    Generic,
    List,
    Mapping,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
)
from support.lib.framework import data_type, operation
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")


@data_type
@dataclass
class DAGError(Exception):
    """Base exception for all DAG engine errors."""

    message: str

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class CycleError(DAGError):
    """Error raised when a dependency cycle is detected within the DAG."""

    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Error raised when a referenced node identifier does not exist in the DAG."""

    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Error raised when attempting to add a node identifier that already exists in the DAG."""

    node_id: str


@data_type
@dataclass
class NodeExecutionError(DAGError):
    """Error raised when an unhandled exception occurs during node action execution."""

    node_id: str
    cause: Exception


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


@data_type
@dataclass(frozen=True)
class NodeDefinition(Generic[T]):
    """Immutable definition of a task node in the directed acyclic graph."""

    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    retries: int = 0


@data_type
@dataclass(frozen=True)
class NodeResult(Generic[T]):
    """Outcome record of a node execution."""

    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


@data_type
@dataclass(frozen=True)
class DAGRunReport:
    """Consolidated summary report of an entire DAG execution run."""

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
# LAST_CLEANED: 2026-11-13T21:40:58Z
# LAST_CHANGED: 2026-11-13T21:40:58Z
# CHANGE: Implement DAG engine domain types, error hierarchy, and service interface protocols
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import heapq
import time
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
)
from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_active_scope, get_singleton, singleton
from . import dag_engine_lite


def _extract_cycle(
    candidates: Set[str],
    downstream: Mapping[str, Set[str]],
    registered_nodes: Set[str],
) -> Tuple[str, ...]:
    """Traces a directed cycle among candidate nodes using depth-first search."""
    visited_state: Dict[str, int] = {nid: 0 for nid in candidates}
    cycle_path: List[str] = []

    def dfs(curr: str, stack: List[str]) -> bool:
        visited_state[curr] = 1
        stack.append(curr)
        for nxt in sorted(downstream.get(curr, set())):
            if nxt in candidates and nxt in registered_nodes:
                if visited_state[nxt] == 1:
                    idx = stack.index(nxt)
                    cycle_path.extend(stack[idx:] + [nxt])
                    return True
                if visited_state[nxt] == 0:
                    if dfs(nxt, stack):
                        return True
        stack.pop()
        visited_state[curr] = 2
        return False

    for nid in sorted(candidates):
        if visited_state[nid] == 0:
            if dfs(nid, []):
                break

    return tuple(cycle_path)


@singleton
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph."""

    tier = "system"

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    @operation
    @override
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        """Adds a task node to the graph, deferring dependency existence checks."""
        # Reject duplicate node registrations.
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' is already registered in the DAG",
                node_id=node_id,
            )

        # Build immutable node definition with frozen dependencies.
        deps: FrozenSet[str] = (
            frozenset(dependencies) if dependencies is not None else frozenset()
        )
        definition = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())

        # Record directed dependency edges without eagerly validating upstream existence.
        for dep_id in deps:
            self._upstream[node_id].add(dep_id)
            self._downstream.setdefault(dep_id, set()).add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        # Ensure both endpoint nodes are registered.
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Upstream node '{upstream_id}' does not exist in the DAG",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Downstream node '{downstream_id}' does not exist in the DAG",
                node_id=downstream_id,
            )

        # Update adjacency sets and keep immutable node definition synchronized.
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)
        existing = self._nodes[downstream_id]
        if upstream_id not in existing.dependencies:
            self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
                node_id=existing.node_id,
                action=existing.action,
                dependencies=existing.dependencies | frozenset([upstream_id]),
                priority=existing.priority,
                retries=existing.retries,
            )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        # Ensure target node exists prior to removal.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' does not exist in the DAG",
                node_id=node_id,
            )

        # Detach node from upstream dependents and downstream dependencies.
        for up_id in list(self._upstream.get(node_id, set())):
            if up_id in self._downstream:
                self._downstream[up_id].discard(node_id)
                if up_id not in self._nodes and not self._downstream[up_id]:
                    del self._downstream[up_id]

        for down_id in list(self._downstream.get(node_id, set())):
            if down_id in self._upstream:
                self._upstream[down_id].discard(node_id)
            if down_id in self._nodes:
                down_def = self._nodes[down_id]
                if node_id in down_def.dependencies:
                    self._nodes[down_id] = dag_engine_lite.NodeDefinition(
                        node_id=down_def.node_id,
                        action=down_def.action,
                        dependencies=down_def.dependencies - frozenset([node_id]),
                        priority=down_def.priority,
                        retries=down_def.retries,
                    )

        # Delete node definition and adjacency records.
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

        # Purge removed node from active scheduler state when WaveScheduler is registered in scope.
        scope = get_active_scope()
        if (
            scope is not None
            and scope.registry.find_descriptor(dag_engine_lite.WaveScheduler)
            is not None
        ):
            scheduler = get_singleton(dag_engine_lite.WaveScheduler)
            if isinstance(scheduler, WaveScheduler):
                scheduler._purge_node(node_id)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' does not exist in the DAG",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' does not exist in the DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' does not exist in the DAG",
                node_id=node_id,
            )
        return {
            dep_id
            for dep_id in self._downstream.get(node_id, set())
            if dep_id in self._nodes
        }

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        # Verify every referenced upstream dependency exists in registered nodes.
        for nid in sorted(self._nodes.keys()):
            for dep_id in sorted(self._upstream.get(nid, set())):
                if dep_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dep_id}' referenced by '{nid}' does not exist in the DAG",
                        node_id=dep_id,
                    )

        # Perform DFS cycle detection across all registered nodes.
        registered = set(self._nodes.keys())
        cycle_tuple = _extract_cycle(registered, self._downstream, registered)
        if cycle_tuple:
            raise dag_engine_lite.CycleError(
                message="Cycle detected in DAG",
                cycle=cycle_tuple,
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        node_set = set(self._nodes.keys())
        # Compute initial in-degree counts over registered nodes.
        in_degree: Dict[str, int] = {
            nid: len(self._upstream.get(nid, set()) & node_set)
            for nid in node_set
        }

        # Enqueue ready nodes ordered by priority descending, then node_id ascending.
        heap: List[Tuple[int, str]] = []
        for nid in node_set:
            if in_degree[nid] == 0:
                heapq.heappush(heap, (-self._nodes[nid].priority, nid))

        order: List[str] = []
        while heap:
            _, nid = heapq.heappop(heap)
            order.append(nid)
            for dep_id in self._downstream.get(nid, set()):
                if dep_id in in_degree:
                    in_degree[dep_id] -= 1
                    if in_degree[dep_id] == 0:
                        heapq.heappush(
                            heap,
                            (-self._nodes[dep_id].priority, dep_id),
                        )

        # Reconstruct cycle path and raise CycleError when cyclic dependencies block completion.
        if len(order) != len(node_set):
            remaining = node_set - set(order)
            cycle_tuple = _extract_cycle(remaining, self._downstream, node_set)
            raise dag_engine_lite.CycleError(
                message="Cycle detected in DAG",
                cycle=cycle_tuple if cycle_tuple else tuple(sorted(remaining)),
            )

        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {
            nid
            for nid in self._nodes
            if not self._upstream.get(nid, set())
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {
            nid
            for nid in self._nodes
            if not (self._downstream.get(nid, set()) & self._nodes.keys())
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        topological_order = self.topological_sort()
        if not topological_order:
            return [], 0.0

        registered = set(self._nodes.keys())
        earliest_finish: Dict[str, float] = {}
        best_parent: Dict[str, Optional[str]] = {}

        # Accumulate earliest completion times along topological order.
        for nid in topological_order:
            dur = (
                float(estimated_durations[nid])
                if estimated_durations is not None and nid in estimated_durations
                else 1.0
            )
            preds = self._upstream.get(nid, set()) & registered
            if not preds:
                earliest_finish[nid] = dur
                best_parent[nid] = None
            else:
                best_p = max(
                    preds,
                    key=lambda p: (earliest_finish.get(p, 0.0), p),
                )
                earliest_finish[nid] = earliest_finish.get(best_p, 0.0) + dur
                best_parent[nid] = best_p

        # Identify maximal terminal node and backtrack along predecessors.
        max_leaf = max(
            topological_order,
            key=lambda n: (earliest_finish[n], n),
        )
        max_duration = earliest_finish[max_leaf]

        path: List[str] = []
        curr: Optional[str] = max_leaf
        while curr is not None:
            path.append(curr)
            curr = best_parent.get(curr)
        path.reverse()

        return path, max_duration


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = "system"

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _resolve_dag(self) -> dag_engine_lite.DAG:
        """Resolves and caches the active DAG singleton in the current scope."""
        dag = get_singleton(dag_engine_lite.DAG)
        self._dag = dag
        return dag

    def _purge_node(self, node_id: str) -> None:
        """Purges a removed node from internal scheduler state."""
        self._states.pop(node_id, None)

    def _sync_states(self) -> dag_engine_lite.DAG:
        """Synchronizes internal state map with currently registered DAG nodes."""
        dag = self._resolve_dag()
        current_nodes = dag.all_nodes()

        # Remove stale entries for nodes deleted from the DAG.
        for stale_id in list(self._states.keys()):
            if stale_id not in current_nodes:
                with unreachable:
                    del self._states[stale_id]

        # First pass: initialize newly discovered nodes so upstream states exist for reconciliation.
        roots = dag.find_roots()
        for nid in current_nodes:
            if nid not in self._states:
                if nid in roots:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

        # Second pass: reconcile PENDING and READY states against current upstream dependencies.
        for nid in current_nodes:
            state = self._states[nid]
            if state == dag_engine_lite.NodeState.PENDING:
                deps = dag.get_dependencies(nid)
                if not deps or all(
                    self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED
                    for d in deps
                ):
                    self._states[nid] = dag_engine_lite.NodeState.READY
            elif state == dag_engine_lite.NodeState.READY:
                deps = dag.get_dependencies(nid)
                if deps and not all(
                    self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED
                    for d in deps
                ):
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

        return dag

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        dag = self._sync_states()
        ready_candidates: List[str] = []

        for nid, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                deps = dag.get_dependencies(nid)
                if all(
                    self._states.get(dep_id) == dag_engine_lite.NodeState.SUCCEEDED
                    for dep_id in deps
                ):
                    ready_candidates.append(nid)

        # Order ready nodes by priority descending, then node_id ascending.
        ready_candidates.sort(
            key=lambda nid: (-dag.get_node(nid).priority, nid)
        )
        return ready_candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        dag = self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED

        # Promote newly unblocked PENDING dependents to READY.
        for dep_id in dag.get_dependents(node_id):
            if self._states.get(dep_id) == dag_engine_lite.NodeState.PENDING:
                upstream_deps = dag.get_dependencies(dep_id)
                if all(
                    self._states.get(up_id) == dag_engine_lite.NodeState.SUCCEEDED
                    for up_id in upstream_deps
                ):
                    self._states[dep_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        dag = self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Cancel all remaining non-terminal nodes in the graph.
            for nid, st in list(self._states.items()):
                if st not in terminal_states:
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            # Traverse transitive downstream dependents and mark non-terminal ones SKIPPED.
            queue: List[str] = list(dag.get_dependents(node_id))
            visited: Set[str] = set()
            while queue:
                curr = queue.pop(0)
                if curr in visited:
                    continue
                visited.add(curr)
                if self._states.get(curr) not in terminal_states:
                    self._states[curr] = dag_engine_lite.NodeState.SKIPPED
                for nxt in dag.get_dependents(curr):
                    if nxt not in visited:
                        queue.append(nxt)

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states or are blocked by failure."""
        dag = self._sync_states()
        if not self._states:
            return True

        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        # If every node is in a terminal state, execution is finished.
        if all(st in terminal_states for st in self._states.values()):
            return True

        # If any node is currently READY or RUNNING, execution is still in progress.
        for st in self._states.values():
            if st in (
                dag_engine_lite.NodeState.READY,
                dag_engine_lite.NodeState.RUNNING,
            ):
                return False

        # Only PENDING nodes remain; check if all of them are transitively blocked by failure/skip/cancel.
        failed_or_blocked = {
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        def is_blocked(nid: str, seen: Set[str]) -> bool:
            if nid in seen:
                return False
            seen.add(nid)
            for up_id in dag.get_dependencies(nid):
                up_state = self._states.get(up_id)
                if up_state in failed_or_blocked:
                    return True
                if up_state == dag_engine_lite.NodeState.PENDING and is_blocked(
                    up_id, seen
                ):
                    return True
            return False

        for nid, st in self._states.items():
            if st == dag_engine_lite.NodeState.PENDING:
                if not is_blocked(nid, set()):
                    return False

        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        dag = self._sync_states()
        if node_id not in dag.all_nodes():
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' is not registered in the DAG",
                node_id=node_id,
            )
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node currently registered in the graph."""
        dag = self._sync_states()
        registered = dag.all_nodes()
        return {
            nid: st for nid, st in self._states.items() if nid in registered
        }


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

    tier = "system"

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._scheduler: Optional[dag_engine_lite.WaveScheduler] = None
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._dag = dag
        self._scheduler = scheduler

        # Validate graph completeness and acyclicity before commencing waves.
        dag.validate()

        self._results = {}
        run_start = time.perf_counter()
        halted = False

        # Execute waves sequentially until finished or halted by FAIL_FAST.
        while not halted and not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                with unreachable:
                    break

            for node_id in wave:
                # Skip nodes that may have transitioned to terminal state mid-wave.
                current_state = scheduler.get_state(node_id)
                if current_state in (
                    dag_engine_lite.NodeState.CANCELLED,
                    dag_engine_lite.NodeState.SKIPPED,
                    dag_engine_lite.NodeState.FAILED,
                    dag_engine_lite.NodeState.SUCCEEDED,
                ):
                    with unreachable:
                        continue

                node_def = dag.get_node(node_id)
                scheduler.mark_running(node_id)

                node_start = time.perf_counter()
                retries_attempted = 0
                last_error: Optional[Exception] = None
                succeeded = False
                return_value: Any = None

                # Attempt node execution with configured retries on exception.
                max_attempts = max(0, node_def.retries) + 1
                for attempt in range(max_attempts):
                    try:
                        return_value = node_def.action()
                        succeeded = True
                        break
                    except Exception as exc:
                        last_error = exc
                        if attempt < max_attempts - 1:
                            retries_attempted += 1

                node_duration = time.perf_counter() - node_start

                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=return_value,
                        error=None,
                        duration_seconds=node_duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=last_error,
                        duration_seconds=node_duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
                        break

        wall_clock_seconds = time.perf_counter() - run_start

        # Populate default NodeResult entries strictly for terminal skipped or cancelled nodes.
        final_states = scheduler.get_all_states()
        for nid, st in final_states.items():
            if nid not in self._results and st in (
                dag_engine_lite.NodeState.SKIPPED,
                dag_engine_lite.NodeState.CANCELLED,
            ):
                self._results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=st,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        # Compute critical path across the graph using default unweighted topology.
        critical_path_list, _ = dag.compute_critical_path(None)

        succeeded_nodes = tuple(
            sorted(
                {
                    nid
                    for nid, res in self._results.items()
                    if res.state == dag_engine_lite.NodeState.SUCCEEDED
                }
                | {
                    nid
                    for nid, st in final_states.items()
                    if st == dag_engine_lite.NodeState.SUCCEEDED
                }
            )
        )
        failed_nodes = tuple(
            sorted(
                {
                    nid
                    for nid, res in self._results.items()
                    if res.state == dag_engine_lite.NodeState.FAILED
                }
                | {
                    nid
                    for nid, st in final_states.items()
                    if st == dag_engine_lite.NodeState.FAILED
                }
            )
        )
        skipped_nodes = tuple(
            sorted(
                {
                    nid
                    for nid, res in self._results.items()
                    if res.state == dag_engine_lite.NodeState.SKIPPED
                }
                | {
                    nid
                    for nid, st in final_states.items()
                    if st == dag_engine_lite.NodeState.SKIPPED
                }
            )
        )
        cancelled_nodes = tuple(
            sorted(
                {
                    nid
                    for nid, res in self._results.items()
                    if res.state == dag_engine_lite.NodeState.CANCELLED
                }
                | {
                    nid
                    for nid, st in final_states.items()
                    if st == dag_engine_lite.NodeState.CANCELLED
                }
            )
        )

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(final_states),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(critical_path_list),
            results=dict(self._results),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-13T22:29:37Z
# LAST_CHANGED: 2026-11-13T22:23:07Z
# CHANGE: Wrap provably unreachable defensive invariant guards in _sync_states and DAGRunner.run with unreachable
# PRETENSE_COVERAGE_AUDIT: 2026-11-13T22:29:37Z
# PRETENSE_QA_AUDIT: 2026-11-13T22:29:07Z
# --- END AUTOFAB METADATA ---
