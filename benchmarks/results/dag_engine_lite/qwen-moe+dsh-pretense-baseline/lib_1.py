# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261029_015150_qwen-moe_dag_engine_lite_pretense_baseline
# Timestamp: 2026-10-29T01:51:50.701795+00:00
# Benchmark Task: dag_engine_lite
# Model: qwen-moe (Tier 1)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 362,903
#   Cached Inbound Tokens:   8,578,197
#   Outbound Tokens:         91,951
#   Total Tokens:            9,033,051
#   Financial Cost ($USD):   $0.0000
#   Wall Clock Duration:     1607.26s
#   Step Latencies (s):      [1396.6, 202.4]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
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
"""Low-level specification for the synchronous DAG execution and wave scheduling engine."""

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

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """
    cycle: Tuple[str, ...]

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """
    node_id: str

    def __str__(self) -> str:
        return self.message


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
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        ...

    @operation
    def validate(self) -> None:
        ...

    @operation
    def topological_sort(self) -> List[str]:
        ...

    @operation
    def find_roots(self) -> Set[str]:
        ...

    @operation
    def find_leaves(self) -> Set[str]:
        ...

    @operation
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        ...


@singleton_type("system")
class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into sequential execution waves."""

    @operation
    def next_wave(self) -> List[str]:
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        ...

    @operation
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> None:
        ...

    @operation
    def is_finished(self) -> bool:
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        ...


@singleton_type("system")
class DAGRunner(Singleton[SystemTier], Protocol):
    """Executes a DAG sequentially to completion under failure policies."""

    @operation
    def run(
        self,
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> DAGRunReport:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T02:18:37Z
# LAST_CHANGED: 2026-10-29T02:18:37Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 94a648d0ec31
# COVERAGE_AUDIT: 2026-10-29T02:18:37Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T02:18:37Z
# PRETENSE_QA_AUDIT: 2026-10-29T02:18:37Z
# QA_AUDIT: 2026-10-29T02:18:37Z
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete realization of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

from support.lib.lifecycle import LifecycleRegistry, get_default_registry
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple, cast

from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton, SystemTier, get_singleton, system

from . import dag_engine_lite


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    """

    tier: SystemTier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    # add_node: Constructs immutable NodeDefinition with frozen dependency set,
    # inserts definition into _nodes, registering empty neighbor sets,
    # adds directed edges from each dependency to node_id (deferred validation)
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
        self._nodes[node_id] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozenset(dependencies or []),
            priority=priority,
            retries=retries,
        )
        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()
        for dep_id in dependencies or []:
            if dep_id not in self._downstream:
                self._downstream[dep_id] = set()
            self._downstream[dep_id].add(node_id)
            self._upstream[node_id].add(dep_id)

    # add_edge: Verifies both nodes exist, raises NodeNotFoundError if missing,
    # updates _upstream and _downstream sets
    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        if upstream_id not in self._nodes or downstream_id not in self._nodes:
            missing = []
            if upstream_id not in self._nodes:
                missing.append(upstream_id)
            if downstream_id not in self._nodes:
                missing.append(downstream_id)
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node(s) {missing} not found in graph",
                node_id=missing[0],
            )
        self._downstream[upstream_id].add(downstream_id)
        self._upstream[downstream_id].add(upstream_id)

    # remove_node: Verifies presence, raises NodeNotFoundError if absent,
    # removes from all incident neighbor sets, deletes from _nodes, _upstream, _downstream
    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        # Remove this node from downstream nodes' upstream sets
        for dependent in list(self._downstream.get(node_id, set())):
            self._upstream[dependent].discard(node_id)
        # Remove this node from upstream nodes' downstream sets
        for dep in list(self._upstream.get(node_id, set())):
            self._downstream[dep].discard(node_id)
        # Delete node entries
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)
        del self._nodes[node_id]

    # has_node: Checks membership of node_id in _nodes
    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    # get_node: Looks up node_id in _nodes, raises NodeNotFoundError if missing
    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        return self._nodes[node_id]

    # get_dependencies: Verifies node_id in _nodes, returns copy of _upstream[node_id]
    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        return set(self._upstream[node_id])

    # get_dependents: Verifies node_id in _nodes, returns copy of _downstream[node_id]
    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in graph",
                node_id=node_id,
            )
        return set(self._downstream[node_id])

    # all_nodes: Returns a copy of set(_nodes.keys())
    @operation
    @override
    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    # validate: Verifies every dependency exists in _nodes,
    # runs DFS cycle detection, raises appropriate errors
    @operation
    @override
    def validate(self) -> None:
        # Verify all dependencies exist
        for node_id, definition in self._nodes.items():
            for dep_id in definition.dependencies:
                if dep_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dep_id}' of node '{node_id}' not found in graph",
                        node_id=dep_id,
                    )
        # DFS cycle detection
        self._detect_cycle()

    def _detect_cycle(self) -> None:
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {nid: WHITE for nid in self._nodes}

        for start in sorted(self._nodes.keys()):
            if color[start] != WHITE:
                continue
            stack: list[tuple[str, bool]] = [(start, False)]
            parent: dict[str, Optional[str]] = {start: None}
            while stack:
                node, returning = stack.pop()
                if returning:
                    color[node] = BLACK
                else:
                    color[node] = GRAY
                    stack.append((node, True))
                    for neighbor in sorted(self._downstream.get(node, set())):
                        if color[neighbor] == GRAY:
                            cycle: list[str] = [neighbor, node]
                            cur = node
                            while cur != neighbor:
                                cur = parent.get(cur)
                                if cur is None or cur == neighbor:
                                    break
                                cycle.append(cur)
                            raise dag_engine_lite.CycleError(
                                message=f"Cycle detected: {' -> '.join(cycle)}",
                                cycle=tuple(cycle),
                            )
                        elif color[neighbor] == WHITE:
                            parent[neighbor] = node
                            stack.append((neighbor, False))

    # topological_sort: Kahn's algorithm with priority desc, node_id asc tie-breaking
    @operation
    @override
    def topological_sort(self) -> List[str]:
        import heapq
        # Compute in-degree counts
        in_degree: Dict[str, int] = {nid: 0 for nid in self._nodes}
        for nid in self._nodes:
            for dep in self._upstream.get(nid, set()):
                if dep in self._nodes:
                    in_degree[nid] += 1
        # Initialize with zero in-degree nodes sorted by priority desc, node_id asc
        heap: list[tuple[int, str]] = []
        for nid in self._nodes:
            if in_degree[nid] == 0:
                node_def = self._nodes[nid]
                heapq.heappush(heap, (-node_def.priority, nid))
        order: List[str] = []
        while heap:
            neg_pri, nid = heapq.heappop(heap)
            order.append(nid)
            for dep in sorted(self._downstream.get(nid, set())):
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        node_def = self._nodes[dep]
                        heapq.heappush(heap, (-node_def.priority, dep))
        if len(order) != len(self._nodes):
            raise dag_engine_lite.CycleError(
                message="Cycle detected in graph",
                cycle=tuple(order),
            )
        return order

    # find_roots: Iterates _nodes, collects those with empty _upstream set
    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {nid for nid in self._nodes if not self._upstream.get(nid)}

    # find_leaves: Iterates _nodes, collects those with empty _downstream set
    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {nid for nid in self._nodes if not self._downstream.get(nid)}

    # compute_critical_path: Computes longest weighted dependency path using topological sort + DP
    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        topo = self.topological_sort()
        durations: Dict[str, float] = {}
        for nid in self._nodes:
            durations[nid] = estimated_durations.get(nid, 1.0) if estimated_durations else 1.0
        # earliest completion: earliest[node] = max(earliest[p] for p in upstream) + duration[node]
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}
        for nid in topo:
            upstream_deps = self._upstream.get(nid, set())
            best_prev: Optional[str] = None
            best_time = 0.0
            for p in upstream_deps:
                if p in earliest and earliest[p] > best_time:
                    best_time = earliest[p]
                    best_prev = p
            earliest[nid] = best_time + durations[nid]
            predecessor[nid] = best_prev
        if not earliest:
            return ([], 0.0)
        # Find terminal node with max completion time
        terminal = max(earliest, key=lambda n: earliest[n])
        # Backtrack through predecessors
        path: List[str] = []
        cur = terminal
        while cur is not None:
            path.append(cur)
            cur = predecessor[cur]
        path.reverse()
        return (path, earliest[terminal])


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states dictionary.
    """

    tier: SystemTier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        """Synchronize _states with all nodes currently registered in _dag.all_nodes()."""
        all_nids = self._dag.all_nodes()
        for nid in all_nids:
            if nid not in self._states:
                deps = self._dag.get_dependencies(nid)
                if not deps:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

    # next_wave: Ensures _states is synced, gathers READY nodes with all deps SUCCEEDED,
    # sorts by priority desc then node_id asc
    @operation
    @override
    def next_wave(self) -> List[str]:
        self._sync_states()
        all_nids = self._dag.all_nodes()
        candidates: List[str] = []
        for nid in all_nids:
            if self._states.get(nid) == dag_engine_lite.NodeState.READY:
                deps = self._dag.get_dependencies(nid)
                if all(
                    self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED
                    for d in deps
                ):
                    candidates.append(nid)
        # Sort by priority descending, then node_id ascending
        candidates.sort(key=lambda nid: (-self._dag.get_node(nid).priority, nid))
        return candidates

    # mark_running: Sets _states[node_id] to RUNNING
    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    # mark_succeeded: Sets to SUCCEEDED, promotes PENDING dependents to READY
    # if all their upstream deps are SUCCEEDED
    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        dependents = self._dag.get_dependents(node_id)
        for dep_id in dependents:
            if self._states[dep_id] == dag_engine_lite.NodeState.PENDING:
                deps = self._dag.get_dependencies(dep_id)
                if all(
                    self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED
                    for d in deps
                ):
                    self._states[dep_id] = dag_engine_lite.NodeState.READY

    # mark_failed: Sets to FAILED, applies failure policy
    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        all_nids = self._dag.all_nodes()

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid in all_nids:
                if self._states.get(nid) in (
                    dag_engine_lite.NodeState.PENDING,
                    dag_engine_lite.NodeState.READY,
                    dag_engine_lite.NodeState.RUNNING,
                ):
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED

        elif failure_policy == dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            self._skip_transitive_dependents(node_id)

        elif failure_policy == dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR:
            # Only skip blocked dependents of failed nodes
            failed_nodes = {
                nid for nid in all_nids
                if self._states.get(nid) == dag_engine_lite.NodeState.FAILED
            }
            for nid in all_nids:
                if self._states.get(nid) not in (
                    dag_engine_lite.NodeState.SUCCEEDED,
                    dag_engine_lite.NodeState.FAILED,
                    dag_engine_lite.NodeState.SKIPPED,
                    dag_engine_lite.NodeState.CANCELLED,
                ):
                    deps = self._dag.get_dependencies(nid)
                    if any(d in failed_nodes for d in deps):
                        self._states[nid] = dag_engine_lite.NodeState.SKIPPED

    def _skip_transitive_dependents(self, node_id: str) -> None:
        """Transition all transitive dependents of node_id to SKIPPED."""
        to_skip: Set[str] = set()
        queue: list[str] = [node_id]
        while queue:
            current = queue.pop()
            dependents = self._dag.get_dependents(current)
            for dep in dependents:
                if dep not in to_skip:
                    to_skip.add(dep)
                    queue.append(dep)
        for nid in to_skip:
            if self._states.get(nid) not in (
                dag_engine_lite.NodeState.SUCCEEDED,
                dag_engine_lite.NodeState.FAILED,
            ):
                self._states[nid] = dag_engine_lite.NodeState.SKIPPED

    # is_finished: Syncs states, checks all nodes are terminal
    @operation
    @override
    def is_finished(self) -> bool:
        self._sync_states()
        terminal = (
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        )
        all_nids = self._dag.all_nodes()
        if not all_nids:
            return True
        for nid in all_nids:
            if self._states.get(nid) not in terminal:
                return False
        return True

    # get_state: Ensures _states contains node_id, returns state
    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        if node_id not in self._states:
            self._sync_states()
        return self._states[node_id]

    # get_all_states: Ensures synced, returns shallow copy filtered to current nodes
    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        current_nodes = self._dag.all_nodes()
        return {
            nid: state
            for nid, state in self._states.items()
            if nid in current_nodes
        }


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine_lite.DAG)
      and WaveScheduler service via get_singleton(dag_engine_lite.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, and _results mapping.
    """

    tier: SystemTier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: dag_engine_lite.WaveScheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    # run: Validates graph, loops waves, executes nodes with retries,
    # collects results, computes critical path, returns DAGRunReport
    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        # Validate graph invariants before execution
        self._dag.validate()
        # Reset scheduler state for fresh execution
        _ws = cast(WaveScheduler, get_singleton(dag_engine_lite.WaveScheduler))
        _ws._states.clear()
        self._scheduler = _ws
        _wall_start = time.monotonic()
        self._results = {}

        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            assert wave, "next_wave() returned empty while is_finished() returned False"

            for node_id in wave:
                node_def = self._dag.get_node(node_id)
                # Mark as running
                self._scheduler.mark_running(node_id)
                _start = time.monotonic()
                result_value: Any = None
                _result_retries: int = 0

                try:
                    for _attempt in range(node_def.retries + 1):
                        try:
                            result_value = node_def.action()
                            break
                        except Exception as exc:
                            _result_retries += 1
                            if _result_retries >= node_def.retries + 1:
                                raise
                    # Success on one of the attempts
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=result_value,
                        duration_seconds=time.monotonic() - _start,
                        retries_attempted=_result_retries,
                    )
                    self._scheduler.mark_succeeded(node_id)
                except Exception as exc:
                    # Failed after exhausting retries
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=exc,
                        duration_seconds=time.monotonic() - _start,
                        retries_attempted=_result_retries,
                    )
                    self._scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        break

        # Populate default results for skipped/cancelled unexecuted nodes
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
                    )

        # Compute critical path
        _critical_path, _ = self._dag.compute_critical_path()

        # Build report
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=tuple(
                nid for nid, r in sorted(self._results.items())
                if r.state == dag_engine_lite.NodeState.SUCCEEDED
            ),
            failed_nodes=tuple(
                nid for nid, r in sorted(self._results.items())
                if r.state == dag_engine_lite.NodeState.FAILED
            ),
            skipped_nodes=tuple(
                nid for nid, r in sorted(self._results.items())
                if r.state == dag_engine_lite.NodeState.SKIPPED
            ),
            cancelled_nodes=tuple(
                nid for nid, r in sorted(self._results.items())
                if r.state == dag_engine_lite.NodeState.CANCELLED
            ),
            wall_clock_seconds=time.monotonic() - _wall_start,
            critical_path=tuple(_critical_path),
            results=self._results,
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-29T02:18:37Z
# LAST_CHANGED: 2026-10-29T02:18:37Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: be937bec41e2
# COVERAGE_AUDIT: 2026-10-29T02:18:37Z
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T02:18:37Z
# PRETENSE_QA_AUDIT: 2026-10-29T02:18:37Z
# QA_AUDIT: 2026-10-29T02:18:37Z
# --- END CLEANROOM METADATA ---
