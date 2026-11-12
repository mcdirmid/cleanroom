# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261111_012033_gemini-flash_dag_engine_lite_combined
# Timestamp: 2026-11-11T01:20:33.234622+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-flash (Tier 2)
# Methodology: combined
# Harness: antigravity
# Run Index: 3
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 4,895,436
#   Cached Inbound Tokens:   93,914,032
#   Outbound Tokens:         664,418
#   Total Tokens:            99,473,886
#   Financial Cost ($USD):   $3.1032
#   Wall Clock Duration:     4915.12s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 9, lib: 10, pretense: 8, pretense_coverage: 6, pretense_qa: 19, qa: 11, test: 4 (Total: 67)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       51
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
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")


@data_type
@dataclass
class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """
    message: str

    def __post_init__(self) -> None:
        super().__init__(self.message)


@data_type
@dataclass
class CycleError(DAGError):
    """Precondition contract violation error raised when a dependency cycle is detected within the DAG.

    Designates an untestable checked precondition violation when caller constructs or validates a cyclic graph.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """
    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Precondition contract violation error raised when a referenced node identifier does not exist in the DAG.

    Designates an untestable checked precondition violation when caller references an unregistered node.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """
    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Precondition contract violation error raised when attempting to add a node identifier that already exists in the DAG.

    Designates an untestable checked precondition violation when caller attempts to add a duplicate node.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the duplicate node.
    """
    node_id: str


@data_type
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


@data_type
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


@data_type
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


@singleton_type("system")
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
# LAST_CLEANED: 2026-11-11T02:21:55Z
# LAST_CHANGED: 2026-11-11T02:21:55Z
# CHANGE: Prune uncontracted __str__ methods on exception classes
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
from __future__ import annotations

import dataclasses
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type, unreachable
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    SystemTier,
    get_default_registry,
    get_singleton,
    system,
)
from . import dag_engine_lite


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph."""

    tier = system

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
        dependencies: Optional[Collection[str]],
        priority: int,
        retries: int,
    ) -> None:
        """Adds a task node to the graph."""
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                f"Node '{node_id}' already registered in graph",
                node_id,
            )
        deps = frozenset(dependencies) if dependencies is not None else frozenset()
        node_def = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = node_def
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
                f"Upstream node '{upstream_id}' not found in graph",
                upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Downstream node '{downstream_id}' not found in graph",
                downstream_id,
            )
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)
        node_def = self._nodes[downstream_id]
        self._nodes[downstream_id] = dataclasses.replace(
            node_def,
            dependencies=frozenset(self._upstream[downstream_id]),
        )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph",
                node_id,
            )
        del self._nodes[node_id]
        up = self._upstream.pop(node_id, set())
        down = self._downstream.pop(node_id, set())
        for u in up:
            if u in self._downstream:
                self._downstream[u].discard(node_id)
        for d in down:
            if d in self._upstream:
                self._upstream[d].discard(node_id)
                if d in self._nodes:
                    self._nodes[d] = dataclasses.replace(
                        self._nodes[d],
                        dependencies=frozenset(self._upstream[d]),
                    )

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
                f"Node '{node_id}' not found in graph",
                node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph",
                node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in graph",
                node_id,
            )
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        return set(self._nodes.keys())

    def _detect_cycle(self) -> Optional[Tuple[str, ...]]:
        visited: Set[str] = set()
        on_path: Dict[str, int] = {}
        path: List[str] = []

        def dfs(u: str) -> Optional[Tuple[str, ...]]:
            for v in sorted(self._downstream.get(u, set())):
                if v not in self._nodes:
                    with unreachable:
                        continue
                if v in on_path:
                    return tuple(path[on_path[v]:] + [v])
                if v not in visited:
                    on_path[v] = len(path)
                    path.append(v)
                    res = dfs(v)
                    path.pop()
                    del on_path[v]
                    if res is not None:
                        return res
            visited.add(u)
            return None

        for node in sorted(self._nodes.keys()):
            if node not in visited:
                on_path[node] = len(path)
                path.append(node)
                res = dfs(node)
                path.pop()
                del on_path[node]
                if res is not None:
                    return res
        return None

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        for nid, node_def in self._nodes.items():
            for dep in node_def.dependencies:
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Referenced dependency '{dep}' for node '{nid}' not found in graph",
                        dep,
                    )
        cycle = self._detect_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                f"Cycle detected: {' -> '.join(cycle)}",
                cycle,
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        in_degrees: Dict[str, int] = {
            nid: len([u for u in self._upstream.get(nid, set()) if u in self._nodes])
            for nid in self._nodes
        }
        ready = [nid for nid, deg in in_degrees.items() if deg == 0]
        ready.sort(key=lambda nid: (-self._nodes[nid].priority, nid))
        order: List[str] = []

        while ready:
            cand = ready.pop(0)
            order.append(cand)
            newly_ready: List[str] = []
            for d in sorted(self._downstream.get(cand, set())):
                if d in in_degrees:
                    in_degrees[d] -= 1
                    if in_degrees[d] == 0:
                        newly_ready.append(d)
            if newly_ready:
                ready.extend(newly_ready)
                ready.sort(key=lambda nid: (-self._nodes[nid].priority, nid))

        if len(order) != len(self._nodes):
            cycle = self._detect_cycle()
            assert cycle is not None
            raise dag_engine_lite.CycleError(
                f"Cycle detected: {' -> '.join(cycle)}",
                cycle,
            )
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {
            nid
            for nid in self._nodes
            if not any(u in self._nodes for u in self._upstream.get(nid, set()))
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {
            nid
            for nid in self._nodes
            if not any(d in self._nodes for d in self._downstream.get(nid, set()))
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        if not self._nodes:
            return ([], 0.0)
        order = self.topological_sort()
        durations: Dict[str, float] = {}
        for nid in self._nodes:
            if estimated_durations is not None and nid in estimated_durations:
                durations[nid] = float(estimated_durations[nid])
            else:
                durations[nid] = 1.0

        earliest: Dict[str, float] = {}
        best_pred: Dict[str, Optional[str]] = {}

        for node in order:
            up = [u for u in self._upstream.get(node, set()) if u in self._nodes]
            if not up:
                earliest[node] = durations[node]
                best_pred[node] = None
            else:
                max_p = min(up, key=lambda p: (-earliest[p], p))
                earliest[node] = earliest[max_p] + durations[node]
                best_pred[node] = max_p

        best_end = min(self._nodes.keys(), key=lambda n: (-earliest[n], n))
        max_duration = earliest[best_end]

        path: List[str] = []
        curr: Optional[str] = best_end
        while curr is not None:
            path.append(curr)
            curr = best_pred[curr]
        path.reverse()
        return (path, max_duration)


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = system

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @property
    def _dag(self) -> dag_engine_lite.DAG:
        return get_singleton(dag_engine_lite.DAG)

    def _sync_states(self) -> None:
        dag = self._dag
        all_nodes = dag.all_nodes()
        roots = dag.find_roots()
        for nid in list(self._states.keys()):
            if nid not in all_nodes:
                del self._states[nid]
        for nid in all_nodes:
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
        dag = self._dag
        candidates: List[str] = []
        for nid, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                deps = dag.get_dependencies(nid)
                if all(self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED for d in deps):
                    candidates.append(nid)
        candidates.sort(key=lambda nid: (-dag.get_node(nid).priority, nid))
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        dag = self._dag
        for dep in dag.get_dependents(node_id):
            if self._states.get(dep) == dag_engine_lite.NodeState.PENDING:
                up = dag.get_dependencies(dep)
                if all(self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in up):
                    self._states[dep] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        dag = self._dag
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid in dag.all_nodes():
                if nid != node_id and self._states.get(nid) not in terminal_states:
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            queue = list(dag.get_dependents(node_id))
            visited = set(queue)
            while queue:
                curr = queue.pop(0)
                if self._states.get(curr) not in terminal_states:
                    self._states[curr] = dag_engine_lite.NodeState.SKIPPED
                for nxt in dag.get_dependents(curr):
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        self._sync_states()
        dag = self._dag
        all_nodes = dag.all_nodes()
        if not all_nodes:
            return True
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        if all(self._states.get(nid) in terminal_states for nid in all_nodes):
            return True
        if any(self._states.get(nid) == dag_engine_lite.NodeState.RUNNING for nid in all_nodes):
            return False
        return len(self.next_wave()) == 0

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        if not self._dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not found in scheduled DAG",
                node_id,
            )
        if node_id not in self._states:
            self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._sync_states()
        all_nodes = self._dag.all_nodes()
        return {k: v for k, v in self._states.items() if k in all_nodes}


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

    tier = system

    def __init__(self) -> None:
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @property
    def _dag(self) -> dag_engine_lite.DAG:
        return get_singleton(dag_engine_lite.DAG)

    @property
    def _scheduler(self) -> dag_engine_lite.WaveScheduler:
        return get_singleton(dag_engine_lite.WaveScheduler)

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        dag = self._dag
        scheduler = self._scheduler
        dag.validate()

        start_time = time.perf_counter()
        self._results = {}

        halt = False
        while not scheduler.is_finished() and not halt and (wave := scheduler.next_wave()):
            for node_id in wave:
                scheduler.mark_running(node_id)
                node_def = dag.get_node(node_id)
                node_start = time.perf_counter()
                retries_attempted = 0
                node_succeeded = False
                result_value: Any = None
                last_error: Optional[Exception] = None

                for attempt in range(max(0, node_def.retries) + 1):
                    if attempt > 0:
                        retries_attempted += 1
                    try:
                        result_value = node_def.action()
                        node_succeeded = True
                        last_error = None
                        break
                    except Exception as ex:  # cleanroom: allow-broad-exception
                        last_error = ex

                node_duration = time.perf_counter() - node_start
                if node_succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=result_value,
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
                        halt = True
                        break

        # Populate unexecuted nodes from scheduler states
        for node_id in sorted(dag.all_nodes()):
            if node_id not in self._results:
                state = scheduler.get_state(node_id)
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        wall_clock = time.perf_counter() - start_time
        crit_path_nodes, _ = dag.compute_critical_path(None)

        succeeded_nodes = tuple(
            nid
            for nid, res in self._results.items()
            if res.state == dag_engine_lite.NodeState.SUCCEEDED
        )
        failed_nodes = tuple(
            nid
            for nid, res in self._results.items()
            if res.state == dag_engine_lite.NodeState.FAILED
        )
        skipped_nodes = tuple(
            nid
            for nid, res in self._results.items()
            if res.state == dag_engine_lite.NodeState.SKIPPED
        )
        cancelled_nodes = tuple(
            nid
            for nid, res in self._results.items()
            if res.state == dag_engine_lite.NodeState.CANCELLED
        )

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(crit_path_nodes),
            results=dict(self._results),
        )


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        DAG,
        keys=[DAG, dag_engine_lite.DAG],
        tier=DAG.tier,
    )
    reg.register_singleton(
        WaveScheduler,
        keys=[WaveScheduler, dag_engine_lite.WaveScheduler],
        tier=WaveScheduler.tier,
    )
    reg.register_singleton(
        DAGRunner,
        keys=[DAGRunner, dag_engine_lite.DAGRunner],
        tier=DAGRunner.tier,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-11T02:42:25Z
# LAST_CHANGED: 2026-11-11T02:40:51Z
# CHANGE: Prune redundant eager terminal failure guard in is_finished, returning directly from next_wave emptiness check
# COVERAGE_AUDIT: 2026-11-11T02:42:20Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-11T02:42:25Z
# PRETENSE_QA_AUDIT: 2026-11-11T02:41:37Z
# QA_AUDIT: 2026-11-11T02:41:51Z
# --- END AUTOFAB METADATA ---
