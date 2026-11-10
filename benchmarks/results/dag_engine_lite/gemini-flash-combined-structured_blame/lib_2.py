# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261109_222451_gemini-flash_dag_engine_lite_combined
# Timestamp: 2026-11-09T22:24:51.385610+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-flash (Tier 2)
# Methodology: combined
# Harness: antigravity
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 2,043,295
#   Cached Inbound Tokens:   34,010,329
#   Outbound Tokens:         360,658
#   Total Tokens:            36,414,282
#   Financial Cost ($USD):   $1.1989
#   Wall Clock Duration:     2108.50s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 5, lib: 5, pretense: 3, pretense_coverage: 2, pretense_qa: 10, qa: 5, test: 1 (Total: 31)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       41
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
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
    Sequence,
    Set,
    Tuple,
    TypeVar,
)
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

    def __str__(self) -> str:
        return self.message


@data_type
@dataclass
class CycleError(DAGError):
    """Precondition contract violation error raised when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """
    cycle: Tuple[str, ...]


@data_type
@dataclass
class NodeNotFoundError(DAGError):
    """Precondition contract violation error raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """
    node_id: str


@data_type
@dataclass
class DuplicateNodeError(DAGError):
    """Precondition contract violation error raised when attempting to add a node identifier that already exists in the DAG.

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
        estimated_durations: Optional[Mapping[str, float]],
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
        failure_policy: FailurePolicy,
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
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T22:32:28Z
# LAST_CHANGED: 2026-11-09T22:32:28Z
# CHANGE: Initial implementation of dag_engine_lite interface module
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Implementation module for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

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
    Sequence,
    Set,
    Tuple,
)
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleTier,
    SystemTier,
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

    tier: LifecycleTier = system

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
                f"Node '{node_id}' already exists in the graph.",
                node_id=node_id,
            )

        deps: FrozenSet[str] = (
            frozenset(dependencies) if dependencies is not None else frozenset()
        )
        defn = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = defn
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
                f"Upstream node '{upstream_id}' does not exist in graph.",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Downstream node '{downstream_id}' does not exist in graph.",
                node_id=downstream_id,
            )

        self._downstream[upstream_id].add(downstream_id)
        self._upstream[downstream_id].add(upstream_id)

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in graph.",
                node_id=node_id,
            )

        if node_id in self._upstream:
            for up in self._upstream[node_id]:
                if up in self._downstream:
                    self._downstream[up].discard(node_id)
            del self._upstream[node_id]

        if node_id in self._downstream:
            for down in self._downstream[node_id]:
                if down in self._upstream:
                    self._upstream[down].discard(node_id)
            del self._downstream[node_id]

        del self._nodes[node_id]

        for s in self._upstream.values():
            s.discard(node_id)
        for s in self._downstream.values():
            s.discard(node_id)

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
                f"Node '{node_id}' does not exist in graph.",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in graph.",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' does not exist in graph.",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        return set(self._nodes.keys())

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        visited: Set[str] = set()
        path: List[str] = []
        path_indices: Dict[str, int] = {}

        def dfs(u: str) -> Optional[Tuple[str, ...]]:
            visited.add(u)
            path_indices[u] = len(path)
            path.append(u)
            for v in sorted(self._downstream.get(u, set())):
                if v in path_indices:
                    return tuple(path[path_indices[v]:] + [v])
                if v not in visited:
                    res = dfs(v)
                    if res is not None:
                        return res
            path.pop()
            del path_indices[u]
            return None

        for start in sorted(self._nodes.keys()):
            if start not in visited:
                cycle = dfs(start)
                if cycle is not None:
                    return cycle
        return None

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        for node_id, defn in self._nodes.items():
            for dep in defn.dependencies:
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Referenced dependency '{dep}' for node '{node_id}' does not exist.",
                        node_id=dep,
                    )


        cycle = self._find_cycle()
        if cycle is not None:
            cycle_str = " -> ".join(cycle)
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected in graph: {cycle_str}",
                cycle=cycle,
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, set()))
            for node_id in self._nodes
        }

        ready: List[str] = [n for n, deg in in_degree.items() if deg == 0]
        ready.sort(key=lambda n: (-self._nodes[n].priority, n))

        ordered: List[str] = []
        while ready:
            curr = ready.pop(0)
            ordered.append(curr)

            newly_ready: List[str] = []
            for down in sorted(self._downstream.get(curr, set())):
                if down in in_degree:
                    in_degree[down] -= 1
                    if in_degree[down] == 0:
                        newly_ready.append(down)

            for nr in newly_ready:
                ready.append(nr)
            ready.sort(key=lambda n: (-self._nodes[n].priority, n))

        if len(ordered) != len(self._nodes):
            cycle = self._find_cycle()
            cycle_tuple = cycle if cycle is not None else tuple(self._nodes.keys())
            cycle_str = " -> ".join(cycle_tuple)
            raise dag_engine_lite.CycleError(
                f"Dependency cycle detected during topological sort: {cycle_str}",
                cycle=cycle_tuple,
            )

        return ordered

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {
            node_id
            for node_id in self._nodes
            if not self._upstream.get(node_id)
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {
            node_id
            for node_id in self._nodes
            if not self._downstream.get(node_id)
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

        topo = self.topological_sort()
        durations: Dict[str, float] = {}
        for nid in topo:
            if estimated_durations is not None and nid in estimated_durations:
                durations[nid] = float(estimated_durations[nid])
            else:
                durations[nid] = 1.0

        earliest: Dict[str, float] = {}
        best_pred: Dict[str, Optional[str]] = {}

        for nid in topo:
            up_nodes = [p for p in self._upstream.get(nid, set()) if p in self._nodes]
            if not up_nodes:
                earliest[nid] = durations[nid]
                best_pred[nid] = None
            else:
                sorted_up = sorted(up_nodes)
                best_p = max(sorted_up, key=lambda p: earliest[p])
                earliest[nid] = earliest[best_p] + durations[nid]
                best_pred[nid] = best_p

        max_time = max(earliest.values())
        terminal_candidates = sorted([nid for nid in topo if earliest[nid] == max_time])
        best_terminal = terminal_candidates[0]

        path: List[str] = []
        curr: Optional[str] = best_terminal
        while curr is not None:
            path.append(curr)
            curr = best_pred[curr]
        path.reverse()
        return (path, max_time)


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states dictionary mapping node identifiers to dag_engine_lite.NodeState.
    - Synchronizes dynamic node state by discovering registered nodes from _dag.all_nodes(), initializing root nodes to dag_engine_lite.NodeState.READY and non-root nodes to dag_engine_lite.NodeState.PENDING.
    """

    tier: LifecycleTier = system

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @property
    def _dag(self) -> dag_engine_lite.DAG:
        return get_singleton(dag_engine_lite.DAG)

    def _sync_states(self) -> None:
        all_nodes = self._dag.all_nodes()
        for nid in list(self._states.keys()):
            if nid not in all_nodes:
                del self._states[nid]
        for nid in all_nodes:
            if nid not in self._states:
                deps = self._dag.get_dependencies(nid)
                if not deps:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        self._sync_states()
        candidates: List[str] = []
        for nid, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                deps = self._dag.get_dependencies(nid)
                if all(
                    self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED
                    for d in deps
                ):
                    candidates.append(nid)

        candidates.sort(key=lambda n: (-self._dag.get_node(n).priority, n))
        return candidates

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
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED

        for dep_id in self._dag.get_dependents(node_id):
            if self._states.get(dep_id) == dag_engine_lite.NodeState.PENDING:
                upstream = self._dag.get_dependencies(dep_id)
                if all(
                    self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED
                    for u in upstream
                ):
                    self._states[dep_id] = dag_engine_lite.NodeState.READY

    def _get_transitive_dependents(self, start_id: str) -> Set[str]:
        visited: Set[str] = set()
        queue = list(self._dag.get_dependents(start_id))
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                for nxt in self._dag.get_dependents(curr):
                    if nxt not in visited:
                        queue.append(nxt)
        return visited

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid in list(self._states.keys()):
                if nid != node_id and self._states[nid] not in terminal_states:
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            transitive = self._get_transitive_dependents(node_id)
            for dep in transitive:
                if self._states.get(dep) not in terminal_states:
                    self._states[dep] = dag_engine_lite.NodeState.SKIPPED

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        self._sync_states()
        all_nodes = self._dag.all_nodes()
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        return all(self._states.get(n) in terminal_states for n in all_nodes)

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        self._sync_states()
        if node_id not in self._dag.all_nodes():
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' not registered in DAG.",
                node_id=node_id,
            )
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._sync_states()
        all_nodes = self._dag.all_nodes()
        return {
            nid: self._states[nid]
            for nid in all_nodes
            if nid in self._states
        }


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine_lite.DAG) and WaveScheduler service via get_singleton(dag_engine_lite.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, and _results mapping.
    """

    tier: LifecycleTier = system

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
        self._dag.validate()

        start_time = time.monotonic()
        self._results = {}
        any_failed = False

        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:  # pragma: no cover (assumption: halt wave loop when next wave is empty per grounding)
                break  # pragma: no cover (assumption: halt wave loop when next wave is empty per grounding)
            for node_id in wave:
                self._scheduler.mark_running(node_id)
                defn = self._dag.get_node(node_id)
                action = defn.action
                max_retries = defn.retries
                retries_attempted = 0
                node_start = time.monotonic()
                success = False
                val: Any = None
                last_err: Optional[Exception] = None

                while True:
                    try:
                        val = action()
                        success = True
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        last_err = exc
                        if retries_attempted < max_retries:
                            retries_attempted += 1
                        else:
                            break

                node_duration = time.monotonic() - node_start

                if success:
                    res = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=val,
                        error=None,
                        duration_seconds=node_duration,
                        retries_attempted=retries_attempted,
                    )
                    self._results[node_id] = res
                    self._scheduler.mark_succeeded(node_id)
                else:
                    any_failed = True
                    res = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=last_err,
                        duration_seconds=node_duration,
                        retries_attempted=retries_attempted,
                    )
                    self._results[node_id] = res
                    self._scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        break

            if any_failed and failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                break

        states = self._scheduler.get_all_states()
        for nid in sorted(states.keys()):
            if nid not in self._results:
                self._results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=states[nid],
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        crit_nodes, _ = self._dag.compute_critical_path(None)
        critical_path = tuple(crit_nodes)
        wall_clock = time.monotonic() - start_time

        succeeded = tuple(
            nid
            for nid, r in self._results.items()
            if r.state == dag_engine_lite.NodeState.SUCCEEDED
        )
        failed = tuple(
            nid
            for nid, r in self._results.items()
            if r.state == dag_engine_lite.NodeState.FAILED
        )
        skipped = tuple(
            nid
            for nid, r in self._results.items()
            if r.state == dag_engine_lite.NodeState.SKIPPED
        )
        cancelled = tuple(
            nid
            for nid, r in self._results.items()
            if r.state == dag_engine_lite.NodeState.CANCELLED
        )

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=wall_clock,
            critical_path=critical_path,
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
# LAST_CLEANED: 2026-11-09T22:59:57Z
# LAST_CHANGED: 2026-11-09T22:59:00Z
# CHANGE: Prune unreachable defensive adjacency sets, redundant upstream validation, uncontracted dependency checks in topological_sort, and uncontracted scheduler node presence branches
# COVERAGE_AUDIT: 2026-11-09T22:59:43Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T22:59:57Z
# PRETENSE_QA_AUDIT: 2026-11-09T22:59:31Z
# QA_AUDIT: 2026-11-09T22:59:24Z
# --- END AUTOFAB METADATA ---
