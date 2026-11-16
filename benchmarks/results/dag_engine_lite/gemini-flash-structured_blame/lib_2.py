# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261116_014718_gemini-flash_dag_engine_lite
# Timestamp: 2026-11-16T01:47:18.283337+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-flash (Tier 2)
# Methodology: autofab
# Harness: antigravity
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 638,630
#   Cached Inbound Tokens:   9,310,382
#   Outbound Tokens:         184,591
#   Total Tokens:            10,133,603
#   Financial Cost ($USD):   $0.3705
#   Wall Clock Duration:     1310.85s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 3, lib: 2, qa: 3, test: 3 (Total: 11)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       61
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")


@data_type
@dataclass
class DAGError(Exception):
    """Base exception for all DAG engine errors."""
    message: str = ""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the DAG."""
    cycle: Tuple[str, ...] = ()

    def __init__(self, message: str = "", cycle: Tuple[str, ...] = ()) -> None:
        if not message and cycle:
            message = f"Cycle detected in DAG: {' -> '.join(cycle)}"
        super().__init__(message)
        self.message = message
        self.cycle = cycle

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG."""
    node_id: str = ""

    def __init__(self, message: str = "", node_id: str = "") -> None:
        if not message and node_id:
            message = f"Node '{node_id}' not found in DAG"
        super().__init__(message)
        self.message = message
        self.node_id = node_id

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Raised when attempting to add a node identifier that already exists in the DAG."""
    node_id: str = ""

    def __init__(self, message: str = "", node_id: str = "") -> None:
        if not message and node_id:
            message = f"Node '{node_id}' already registered in DAG"
        super().__init__(message)
        self.message = message
        self.node_id = node_id

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class NodeExecutionError(DAGError):
    """Raised when an unhandled exception occurs during node action execution."""
    node_id: str = ""
    cause: Exception = Exception()

    def __init__(self, message: str = "", node_id: str = "", cause: Optional[Exception] = None) -> None:
        if cause is None:
            cause = Exception("Unknown execution failure")
        if not message:
            message = f"Execution failed for node '{node_id}': {cause}"
        super().__init__(message)
        self.message = message
        self.node_id = node_id
        self.cause = cause

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


@singleton_type("system")
class DAG(Singleton[SystemTier], Protocol):
    """Directed Acyclic Graph holding task nodes and directed dependency edges."""

    @operation
    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
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
    def all_dependencies_exist(self) -> bool:
        """Test-only observability query returning whether all referenced dependencies exist."""
        ...

    @operation
    def is_acyclic(self) -> bool:
        """Test-only observability query returning whether the graph contains no directed cycles."""
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
        """Returns all root nodes with in-degree zero."""
        ...

    @operation
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        ...

    @operation
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        ...


@singleton_type("system")
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


@singleton_type("system")
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
# LAST_CLEANED: 2026-11-16T01:55:14Z
# LAST_CHANGED: 2026-11-16T01:55:14Z
# CHANGES:
# - [2026-11-16T01:55:14Z] [kind:new] [Lines: 1-2, 5-299] Delta: Define DAG interface protocols, error hierarchy, and domain data models | Why: Fulfill low/dag_engine_lite.pyi interface specification
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Synchronous DAG execution and wave scheduling engine implementation."""

from __future__ import annotations

import heapq
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from support.lib.framework import operation, override, unreachable
from support.lib.lifecycle import get_singleton, singleton

from . import dag_engine_lite


def _kahn_topological_sort(
    nodes: Collection[str],
    upstream: Mapping[str, Set[str]],
    downstream: Mapping[str, Set[str]],
    priorities: Mapping[str, float],
    cycle_error_cls: type[dag_engine_lite.CycleError],
) -> List[str]:
    """Computes deterministic topological ordering using Kahn's algorithm with max-heap priority queue."""
    node_set = set(nodes)
    in_degree: Dict[str, int] = {nid: len(upstream.get(nid, set()) & node_set) for nid in node_set}

    heap: List[Tuple[float, str]] = []
    for nid in sorted(node_set):
        if in_degree[nid] == 0:
            heapq.heappush(heap, (-priorities.get(nid, 0.0), nid))

    order: List[str] = []
    while heap:
        neg_pri, nid = heapq.heappop(heap)
        order.append(nid)
        for dep_id in sorted(downstream.get(nid, set())):
            if dep_id in in_degree:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    heapq.heappush(heap, (-priorities.get(dep_id, 0.0), dep_id))

    if len(order) != len(node_set):
        remaining = node_set - set(order)
        visited_state: Dict[str, int] = {nid: 0 for nid in remaining}
        cycle_path: List[str] = []

        def dfs(curr: str, stack: List[str]) -> bool:
            visited_state[curr] = 1
            stack.append(curr)
            for nxt in sorted(downstream.get(curr, set())):
                if nxt in remaining:
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

        for nid in sorted(remaining):
            if visited_state[nid] == 0:
                if dfs(nid, []):
                    break

        raise cycle_error_cls(
            message=f"Cycle detected in DAG: {' -> '.join(cycle_path)}" if cycle_path else "Cycle detected in DAG",
            cycle=tuple(cycle_path) if cycle_path else tuple(sorted(remaining)),
        )

    return order


def _compute_critical_path_dp(
    topological_order: Sequence[str],
    upstream: Mapping[str, Set[str]],
    durations: Optional[Mapping[str, float]] = None,
) -> Tuple[List[str], float]:
    """Computes the longest weighted critical path through a DAG."""
    if not topological_order:
        return [], 0.0

    earliest_finish: Dict[str, float] = {}
    best_parent: Dict[str, Optional[str]] = {}

    for nid in topological_order:
        dur = durations.get(nid, 1.0) if durations is not None else 1.0
        preds = upstream.get(nid, set()) & set(topological_order)
        if not preds:
            earliest_finish[nid] = dur
            best_parent[nid] = None
        else:
            best_p = max(preds, key=lambda p: (earliest_finish.get(p, 0.0), p))
            earliest_finish[nid] = earliest_finish.get(best_p, 0.0) + dur
            best_parent[nid] = best_p

    max_leaf = max(topological_order, key=lambda n: (earliest_finish[n], n))
    max_duration = earliest_finish[max_leaf]

    path: List[str] = []
    curr: Optional[str] = max_leaf
    while curr is not None:
        path.append(curr)
        curr = best_parent.get(curr)
    path.reverse()

    return path, max_duration


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
        """Adds a task node to the graph."""
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' already registered in DAG",
                node_id=node_id,
            )
        deps = frozenset(dependencies) if dependencies else frozenset()
        definition: dag_engine_lite.NodeDefinition[Any] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()
        for dep in deps:
            self._upstream[node_id].add(dep)
            if dep not in self._downstream:
                self._downstream[dep] = set()
            self._downstream[dep].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Upstream node '{upstream_id}' not found in DAG",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Downstream node '{downstream_id}' not found in DAG",
                node_id=downstream_id,
            )
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)
        old_def = self._nodes[downstream_id]
        new_deps = old_def.dependencies | {upstream_id}
        self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
            node_id=old_def.node_id,
            action=old_def.action,
            dependencies=new_deps,
            priority=old_def.priority,
            retries=old_def.retries,
        )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        for u in self._upstream.get(node_id, set()):
            self._downstream.get(u, set()).discard(node_id)
        for d in self._downstream.get(node_id, set()):
            self._upstream.get(d, set()).discard(node_id)
            if d in self._nodes:
                old_def = self._nodes[d]
                new_deps = frozenset(x for x in old_def.dependencies if x != node_id)
                self._nodes[d] = dag_engine_lite.NodeDefinition(
                    node_id=old_def.node_id,
                    action=old_def.action,
                    dependencies=new_deps,
                    priority=old_def.priority,
                    retries=old_def.retries,
                )
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

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
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        return set(self._nodes.keys())

    @operation
    @override
    def all_dependencies_exist(self) -> bool:
        """Test-only observability query returning whether all referenced dependencies exist."""
        all_nids = set(self._nodes.keys())
        for node_def in self._nodes.values():
            for dep in node_def.dependencies:
                if dep not in all_nids:
                    return False
        return True

    @operation
    @override
    def is_acyclic(self) -> bool:
        """Test-only observability query returning whether the graph contains no directed cycles."""
        visited: Dict[str, int] = {nid: 0 for nid in self._nodes}

        def dfs(curr: str) -> bool:
            visited[curr] = 1
            for nxt in self._downstream.get(curr, set()):
                if nxt in self._nodes:
                    if visited.get(nxt, 0) == 1:
                        return False
                    if visited.get(nxt, 0) == 0:
                        if not dfs(nxt):
                            return False
            visited[curr] = 2
            return True

        for nid in sorted(self._nodes.keys()):
            if visited[nid] == 0:
                if not dfs(nid):
                    return False
        return True

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        all_nids = set(self._nodes.keys())
        for nid in sorted(self._nodes.keys()):
            for dep in sorted(self._nodes[nid].dependencies):
                if dep not in all_nids:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Referenced dependency '{dep}' for node '{nid}' does not exist in graph",
                        node_id=dep,
                    )
        _kahn_topological_sort(
            nodes=self._nodes.keys(),
            upstream=self._upstream,
            downstream=self._downstream,
            priorities={nid: float(defn.priority) for nid, defn in self._nodes.items()},
            cycle_error_cls=dag_engine_lite.CycleError,
        )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        all_nids = set(self._nodes.keys())
        for nid in sorted(self._nodes.keys()):
            for dep in sorted(self._nodes[nid].dependencies):
                if dep not in all_nids:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Referenced dependency '{dep}' for node '{nid}' does not exist in graph",
                        node_id=dep,
                    )
        return _kahn_topological_sort(
            nodes=self._nodes.keys(),
            upstream=self._upstream,
            downstream=self._downstream,
            priorities={nid: float(defn.priority) for nid, defn in self._nodes.items()},
            cycle_error_cls=dag_engine_lite.CycleError,
        )

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {nid for nid in self._nodes if len(self._upstream.get(nid, set())) == 0}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {nid for nid in self._nodes if len(self._downstream.get(nid, set())) == 0}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        order = self.topological_sort()
        return _compute_critical_path_dp(order, self._upstream, estimated_durations)


@singleton
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""
    tier = "system"

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        dag = get_singleton(dag_engine_lite.DAG)
        current_nodes = dag.all_nodes()
        for nid in list(self._states.keys()):
            if nid not in current_nodes:
                del self._states[nid]
        roots = dag.find_roots()
        for nid in current_nodes:
            if nid not in self._states:
                if nid in roots:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        self._sync_states()
        dag = get_singleton(dag_engine_lite.DAG)
        ready_candidates: List[str] = []
        for nid, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                deps = dag.get_dependencies(nid)
                if all(self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED for d in deps):
                    ready_candidates.append(nid)

        def sort_key(nid: str) -> Tuple[int, str]:
            node_def = dag.get_node(nid)
            return (-node_def.priority, nid)

        ready_candidates.sort(key=sort_key)
        return ready_candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        self._sync_states()
        if node_id not in self._states:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduler",
                node_id=node_id,
            )
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        self._sync_states()
        if node_id not in self._states:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduler",
                node_id=node_id,
            )
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        dag = get_singleton(dag_engine_lite.DAG)
        for dep_id in dag.get_dependents(node_id):
            if self._states.get(dep_id) == dag_engine_lite.NodeState.PENDING:
                upstream_deps = dag.get_dependencies(dep_id)
                if all(self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstream_deps):
                    self._states[dep_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        self._sync_states()
        if node_id not in self._states:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduler",
                node_id=node_id,
            )
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        dag = get_singleton(dag_engine_lite.DAG)

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid, st in list(self._states.items()):
                if nid != node_id and st in (
                    dag_engine_lite.NodeState.PENDING,
                    dag_engine_lite.NodeState.READY,
                    dag_engine_lite.NodeState.RUNNING,
                ):
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            transitive_dependents: Set[str] = set()
            queue = list(dag.get_dependents(node_id))
            while queue:
                curr = queue.pop(0)
                if curr not in transitive_dependents:
                    transitive_dependents.add(curr)
                    queue.extend(dag.get_dependents(curr))
            for dep_id in transitive_dependents:
                if self._states.get(dep_id) in (
                    dag_engine_lite.NodeState.PENDING,
                    dag_engine_lite.NodeState.READY,
                    dag_engine_lite.NodeState.RUNNING,
                ):
                    self._states[dep_id] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        self._sync_states()
        if not self._states:
            return True
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        if all(st in terminal_states for st in self._states.values()):
            return True
        if any(st == dag_engine_lite.NodeState.RUNNING for st in self._states.values()):
            return False
        if len(self.next_wave()) == 0:
            return True
        return False

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        dag = get_singleton(dag_engine_lite.DAG)
        if not dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._sync_states()
        dag = get_singleton(dag_engine_lite.DAG)
        current_nodes = dag.all_nodes()
        return {nid: st for nid, st in self._states.items() if nid in current_nodes}


@singleton
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""
    tier = "system"

    def __init__(self) -> None:
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)

        # Validate invariants before commencing wave execution
        dag.validate()

        start_time = time.perf_counter()
        self._results.clear()
        if isinstance(scheduler, WaveScheduler):
            scheduler._states.clear()

        failed_node_occurred = False

        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:
                with unreachable:
                    break
            for node_id in wave:
                node_def = dag.get_node(node_id)
                scheduler.mark_running(node_id)
                retries_attempted = 0
                node_start = time.perf_counter()
                action_succeeded = False
                action_val: Any = None
                last_error: Optional[Exception] = None

                while True:
                    try:
                        action_val = node_def.action()
                        action_succeeded = True
                        break
                    except Exception as exc:
                        last_error = exc
                        if retries_attempted < node_def.retries:
                            retries_attempted += 1
                        else:
                            break

                node_duration = time.perf_counter() - node_start

                if action_succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=action_val,
                        duration_seconds=node_duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=last_error,
                        duration_seconds=node_duration,
                        retries_attempted=retries_attempted,
                    )
                    scheduler.mark_failed(node_id, failure_policy)
                    failed_node_occurred = True
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        break

            if failed_node_occurred and failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                break

        # Populate unexecuted terminal results for skipped or cancelled nodes
        all_states = scheduler.get_all_states()
        for nid in sorted(all_states.keys()):
            st = all_states[nid]
            if st in (dag_engine_lite.NodeState.SKIPPED, dag_engine_lite.NodeState.CANCELLED):
                if nid not in self._results:
                    self._results[nid] = dag_engine_lite.NodeResult(
                        node_id=nid,
                        state=st,
                        duration_seconds=0.0,
                        retries_attempted=0,
                    )

        total_wall_clock = time.perf_counter() - start_time
        critical_path, _ = dag.compute_critical_path()

        succeeded_nodes = tuple(nid for nid, r in self._results.items() if r.state == dag_engine_lite.NodeState.SUCCEEDED)
        failed_nodes = tuple(nid for nid, r in self._results.items() if r.state == dag_engine_lite.NodeState.FAILED)
        skipped_nodes = tuple(nid for nid, r in self._results.items() if r.state == dag_engine_lite.NodeState.SKIPPED)
        cancelled_nodes = tuple(nid for nid, r in self._results.items() if r.state == dag_engine_lite.NodeState.CANCELLED)

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=total_wall_clock,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-16T02:09:04Z
# LAST_CHANGED: 2026-11-16T02:03:08Z
# CHANGES:
# - [2026-11-16T01:55:24Z] [kind:new] [Lines: 1-2, 5-8, 12-542, 545-623] Delta: Implement DAG, WaveScheduler, and DAGRunner concrete singletons with Kahn's topological sort and critical path analysis | Why: Fulfill low/dag_engine_lite_impl.pyi specification
# - [2026-11-16T02:03:08Z] [kind:fix] [Lines: 9, 543-544] Delta: Wrap defensive empty wave loop breaker in with unreachable block | Why: Resolve coverage feedback for structurally unreachable loop stall guard
# COVERAGE_AUDIT: 2026-11-16T02:09:04Z
# QA_AUDIT: 2026-11-16T02:08:41Z
# --- END AUTOFAB METADATA ---
