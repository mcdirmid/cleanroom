# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261026_210743_gemini-3_8-flash_dag_engine_lite_pretense_baseline
# Timestamp: 2026-10-26T21:07:43.320345+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: antigravity
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 355,499
#   Cached Inbound Tokens:   5,320,683
#   Outbound Tokens:         71,568
#   Total Tokens:            5,747,750
#   Financial Cost ($USD):   $0.1972
#   Wall Clock Duration:     266.35s
#   Step Latencies (s):      []
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       57
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface specification for the synchronous DAG execution and wave scheduling engine."""

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
@dataclass(frozen=True)
class DAGError(Exception):
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """
    message: str


@data_type
@dataclass(frozen=True)
class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the DAG.

    Args:
        message: Diagnostic description of the error.
        cycle: Sequence of node identifiers forming the cycle.
    """
    cycle: Tuple[str, ...]


@data_type
@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG.

    Args:
        message: Diagnostic description of the error.
        node_id: Identifier of the missing node.
    """
    node_id: str


@data_type
@dataclass(frozen=True)
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
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
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
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        ...


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation for the synchronous DAG execution and wave scheduling engine."""

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
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        # Contract: Constructs immutable NodeDefinition with frozen dependency set without eagerly checking dependency existence.
        deps: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
        node_def = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        # Contract: Inserts definition into _nodes, registering empty neighbor sets in _upstream and _downstream if absent.
        self._nodes[node_id] = node_def
        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()

        # Contract: Adds directed edges from each dependency to node_id, deferring existence validation.
        for dep in deps:
            self._upstream[node_id].add(dep)
            if dep not in self._downstream:
                self._downstream[dep] = set()
            self._downstream[dep].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # Contract: Verifies presence of upstream_id and downstream_id in _nodes.
        # Contract: Raises dag_engine_lite.NodeNotFoundError if either identifier is missing.
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

        # Contract: Updates _upstream and _downstream sets.
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

        # Contract: Synchronize immutable NodeDefinition dependencies
        curr = self._nodes[downstream_id]
        if upstream_id not in curr.dependencies:
            self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
                node_id=curr.node_id,
                action=curr.action,
                dependencies=curr.dependencies | {upstream_id},
                priority=curr.priority,
                retries=curr.retries,
            )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # Contract: Verifies presence of node_id in _nodes.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )

        # Contract: Removes node_id from all incident upstream and downstream neighbor sets.
        for dep in list(self._upstream.get(node_id, set())):
            if dep in self._downstream:
                self._downstream[dep].discard(node_id)
        for child in list(self._downstream.get(node_id, set())):
            if child in self._upstream:
                self._upstream[child].discard(node_id)
            if child in self._nodes:
                c_node = self._nodes[child]
                if node_id in c_node.dependencies:
                    self._nodes[child] = dag_engine_lite.NodeDefinition(
                        node_id=c_node.node_id,
                        action=c_node.action,
                        dependencies=frozenset(d for d in c_node.dependencies if d != node_id),
                        priority=c_node.priority,
                        retries=c_node.retries,
                    )

        # Contract: Deletes node_id from _nodes, _upstream, and _downstream.
        self._nodes.pop(node_id, None)
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

        # Contract: MUST purge the node identifier from wave scheduler state tracking.
        try:
            scheduler: Any = get_singleton(dag_engine_lite.WaveScheduler)
            if hasattr(scheduler, "_states") and node_id in scheduler._states:
                del scheduler._states[node_id]
        except Exception:  # pragma: no cover (defensive fallback when scheduler is not active)
            pass

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        # Contract: Checks membership of node_id in _nodes.
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # Contract: Looks up node_id in _nodes. Raises NodeNotFoundError if absent.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # Contract: Verifies node_id in _nodes, raising NodeNotFoundError if missing.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # Contract: Verifies node_id in _nodes, raising NodeNotFoundError if missing.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        # Contract: Returns a copy of set(_nodes.keys()).
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        # Contract: Verifies that every dependency in every node definition exists in _nodes.
        for node_id, node_def in self._nodes.items():
            for dep in node_def.dependencies:
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Missing dependency '{dep}' referenced by node '{node_id}'",
                        node_id=dep,
                    )

        # Contract: Executes depth-first search cycle detection with active recursion path tracking.
        visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
        path: List[str] = []

        def dfs(curr: str) -> None:
            visited[curr] = 1
            path.append(curr)
            for child in sorted(self._downstream.get(curr, set())):
                if child not in self._nodes:  # pragma: no cover (assumption: dependency existence validated)
                    continue
                c_state = visited.get(child, 0)
                if c_state == 1:
                    idx = path.index(child)
                    cycle_tuple = tuple(path[idx:] + [child])
                    raise dag_engine_lite.CycleError(
                        message=f"Cycle detected: {' -> '.join(cycle_tuple)}",
                        cycle=cycle_tuple,
                    )
                elif c_state == 0:
                    dfs(child)
            path.pop()
            visited[curr] = 2

        for nid in sorted(self._nodes.keys()):
            if visited.get(nid, 0) == 0:
                dfs(nid)

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # Contract: Defer missing dependency existence checks to validate() and topological_sort()
        for node_id, node_def in self._nodes.items():
            for dep in node_def.dependencies:
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Missing dependency '{dep}' referenced by node '{node_id}'",
                        node_id=dep,
                    )

        # Contract: Computes in-degree counts from _upstream mapping.
        in_degree: Dict[str, int] = {
            nid: len([p for p in self._upstream.get(nid, set()) if p in self._nodes])
            for nid in self._nodes
        }

        # Contract: Initializes ready list with nodes having in-degree zero, sorted by priority descending then node_id ascending.
        ready = [nid for nid, deg in in_degree.items() if deg == 0]
        ready.sort(key=lambda n: (-self._nodes[n].priority, n))

        ordered: List[str] = []
        while ready:
            # Contract: Iteratively extracts candidate with highest priority, appends to order
            curr = ready.pop(0)
            ordered.append(curr)

            # Contract: Decrements downstream in-degrees
            newly_ready: List[str] = []
            for child in sorted(self._downstream.get(curr, set())):
                if child in in_degree:
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        newly_ready.append(child)

            # Contract: Inserts newly zero in-degree nodes maintaining priority descending then node_id ascending order.
            for nr in newly_ready:
                ready.append(nr)
            ready.sort(key=lambda n: (-self._nodes[n].priority, n))

        # Contract: Raises dag_engine_lite.CycleError containing the cycle sequence if ordered count does not equal len(_nodes).
        if len(ordered) != len(self._nodes):
            self.validate()
            remaining = sorted(set(self._nodes.keys()) - set(ordered))  # pragma: no cover (defensive)
            raise dag_engine_lite.CycleError(  # pragma: no cover (defensive)
                message=f"Cycle detected among remaining nodes: {remaining}",
                cycle=tuple(remaining),
            )

        return ordered

    @operation
    @override
    def find_roots(self) -> Set[str]:
        # Contract: Iterates over _nodes, collecting node identifiers whose _upstream set is empty.
        return {
            nid for nid in self._nodes
            if not any(dep in self._nodes for dep in self._upstream.get(nid, set()))
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        # Contract: Iterates over _nodes, collecting node identifiers whose _downstream set is empty.
        return {
            nid for nid in self._nodes
            if not any(child in self._nodes for child in self._downstream.get(nid, set()))
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        if not self._nodes:
            return ([], 0.0)

        # Contract: Computes topological order using topological_sort().
        topo = self.topological_sort()

        # Contract: Resolves duration weights mapping defaulting to 1.0 for unspecified nodes.
        durations: Dict[str, float] = {}
        for nid in self._nodes:
            if estimated_durations is not None and nid in estimated_durations:
                durations[nid] = float(estimated_durations[nid])
            else:
                durations[nid] = 1.0

        # Contract: Computes earliest completion times using dynamic programming: earliest[node] = max((earliest[p] for p in upstream), default=0.0) + duration[node].
        earliest: Dict[str, float] = {}
        best_pred: Dict[str, Optional[str]] = {}

        for nid in topo:
            preds = [p for p in self._upstream.get(nid, set()) if p in self._nodes]
            if not preds:
                earliest[nid] = durations[nid]
                best_pred[nid] = None
            else:
                best_p = max(
                    preds,
                    key=lambda p: (earliest[p], self._nodes[p].priority, -ord(p[0]) if p else 0),
                )
                earliest[nid] = earliest[best_p] + durations[nid]
                best_pred[nid] = best_p

        # Contract: Identifies terminal node with maximum completion time.
        terminal_node = max(
            topo,
            key=lambda n: (earliest[n], self._nodes[n].priority, -ord(n[0]) if n else 0),
        )

        # Contract: Backtracks through upstream dependencies selecting predecessor yielding maximum earliest time.
        path: List[str] = []
        curr: Optional[str] = terminal_node
        while curr is not None:
            path.append(curr)
            curr = best_pred[curr]

        # Contract: Returns reversed path list and total path duration weight.
        path.reverse()
        return (path, earliest[terminal_node])


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""

    tier = system

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _get_dag(self) -> dag_engine_lite.DAG:
        return get_singleton(dag_engine_lite.DAG)

    def _sync_states(self) -> None:
        # Contract: Synchronizes dynamic node state by discovering registered nodes from _dag.all_nodes(),
        # initializing root nodes to READY and non-root nodes to PENDING.
        dag = self._get_dag()
        active_nodes = dag.all_nodes()
        roots = dag.find_roots()

        # Remove deleted nodes
        for nid in list(self._states.keys()):
            if nid not in active_nodes:
                del self._states[nid]

        # Initialize newly added nodes
        for nid in active_nodes:
            if nid not in self._states:
                if nid in roots:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

    @operation
    @override
    def next_wave(self) -> List[str]:
        # Contract: Ensures _states contains all nodes from _dag, initializing roots to READY and non-roots to PENDING.
        self._sync_states()
        dag = self._get_dag()

        # Contract: Gathers all nodes currently in READY state whose upstream dependencies are all SUCCEEDED.
        ready_candidates: List[str] = []
        for nid, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                deps = dag.get_dependencies(nid)
                if all(self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED for d in deps):
                    ready_candidates.append(nid)

        # Contract: Sorts candidate nodes by definition priority descending, then node_id ascending.
        ready_candidates.sort(
            key=lambda n: (-dag.get_node(n).priority, n)
        )
        return ready_candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        # Contract: Sets _states[node_id] to dag_engine_lite.NodeState.RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        # Contract: Sets _states[node_id] to dag_engine_lite.NodeState.SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        dag = self._get_dag()

        # Contract: Inspects downstream dependents of node_id.
        # Promotes any dependent currently in PENDING to READY if all its upstream dependencies are SUCCEEDED.
        dependents = dag.get_dependents(node_id)
        for dep in dependents:
            if self._states.get(dep) == dag_engine_lite.NodeState.PENDING:
                upstreams = dag.get_dependencies(dep)
                if all(self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstreams):
                    self._states[dep] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        # Contract: Sets _states[node_id] to dag_engine_lite.NodeState.FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        dag = self._get_dag()

        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Contract: Transitions all non-terminal nodes to CANCELLED if failure_policy is FAIL_FAST.
            for nid in list(self._states.keys()):
                if nid != node_id and self._states[nid] not in terminal_states:
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED

        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            # Contract: Traverses transitive downstream dependents and marks non-terminal dependents as SKIPPED.
            queue = list(dag.get_dependents(node_id))
            visited: Set[str] = set()
            while queue:
                curr = queue.pop(0)
                if curr in visited:
                    continue
                visited.add(curr)
                if self._states.get(curr) not in terminal_states:
                    self._states[curr] = dag_engine_lite.NodeState.SKIPPED
                for next_dep in dag.get_dependents(curr):
                    if next_dep not in visited:
                        queue.append(next_dep)

    @operation
    @override
    def is_finished(self) -> bool:
        # Contract: Synchronizes _states with all nodes currently registered in _dag.all_nodes().
        self._sync_states()
        dag = self._get_dag()
        nodes = dag.all_nodes()

        # Contract: WHEN the DAG contains no nodes, MUST return True.
        if not nodes:
            return True

        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        # Contract: WHEN all nodes in the DAG have reached terminal states, MUST return True.
        if all(self._states.get(n) in terminal_states for n in nodes):
            return True

        # Contract: WHEN any node is currently RUNNING or READY, MUST return False.
        if any(self._states.get(n) == dag_engine_lite.NodeState.RUNNING for n in nodes):
            return False

        if any(self._states.get(n) == dag_engine_lite.NodeState.READY for n in nodes):
            return False

        # Contract: WHEN no ready nodes remain and unexecuted nodes are blocked by failed dependencies, MUST return True.
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        # Contract: Ensures _states contains node_id by synchronizing with _dag.all_nodes() if absent.
        self._sync_states()
        dag = self._get_dag()
        if not dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        # Contract: Ensures _states contains all nodes from _dag.all_nodes().
        self._sync_states()
        dag = self._get_dag()
        active = dag.all_nodes()
        # Contract: Returns a shallow copy of _states mapping filtered to only include nodes currently present in _dag.all_nodes().
        return {nid: st for nid, st in self._states.items() if nid in active}


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""

    tier = system

    def __init__(self) -> None:
        pass

    def _get_dag(self) -> dag_engine_lite.DAG:
        return get_singleton(dag_engine_lite.DAG)

    def _get_scheduler(self) -> dag_engine_lite.WaveScheduler:
        return get_singleton(dag_engine_lite.WaveScheduler)

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        dag = self._get_dag()
        scheduler = self._get_scheduler()

        # Contract: Validates _dag using _dag.validate(), allowing cycle or missing dependency exceptions to raise immediately.
        dag.validate()

        # Contract: Initializes start wall-clock time and empty _results mapping.
        start_time = time.time()
        results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

        # Contract: Loops while _scheduler.is_finished() returns False and retrieves the next wave from _scheduler.next_wave().
        halt_execution = False
        while not scheduler.is_finished() and not halt_execution:
            wave = scheduler.next_wave()
            # Contract: Halts wave loop when next wave is empty.
            if not wave:  # pragma: no cover (defensive fallback)
                break

            # Contract: Dispatches each ready wave node sequentially, marking it RUNNING in _scheduler.
            for node_id in wave:
                scheduler.mark_running(node_id)
                node_def = dag.get_node(node_id)

                # Contract: Executes node action with retry attempts up to definition.retries upon exception.
                attempts = 0
                node_start = time.time()
                success = False
                val: Any = None
                last_error: Optional[Exception] = None

                while True:
                    try:
                        val = node_def.action()
                        success = True
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        last_error = exc
                        if attempts < node_def.retries:
                            attempts += 1
                        else:
                            break

                duration = time.time() - node_start

                if success:
                    # Contract: Records NodeResult(SUCCEEDED) and marks SUCCEEDED in _scheduler on success.
                    results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=val,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    # Contract: Records NodeResult(FAILED) and marks FAILED in _scheduler with failure_policy on failure after retries.
                    results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=last_error,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    scheduler.mark_failed(node_id, failure_policy=failure_policy)

                    # Contract: Halts further wave execution when failure_policy is FAIL_FAST and a node has failed.
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halt_execution = True
                        break

        # Contract: Populates _results with default unexecuted NodeResult records for terminal skipped or cancelled nodes from _scheduler states.
        all_states = scheduler.get_all_states()
        for nid, st in all_states.items():
            if nid not in results:
                results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=st,
                )

        # Contract: Computes critical path using _dag.compute_critical_path().
        crit_path, _ = dag.compute_critical_path()
        wall_clock = time.time() - start_time

        # Contract: Gathers succeeded, failed, skipped, and cancelled node tuples from _results and _scheduler states.
        succeeded_nodes = tuple(nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.SUCCEEDED)
        failed_nodes = tuple(nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.FAILED)
        skipped_nodes = tuple(nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.SKIPPED)
        cancelled_nodes = tuple(nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.CANCELLED)

        # Contract: Returns consolidated dag_engine_lite.DAGRunReport.
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(crit_path),
            results=dict(results),
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
