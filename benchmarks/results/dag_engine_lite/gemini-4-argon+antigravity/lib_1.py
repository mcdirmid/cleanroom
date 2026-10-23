# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261023_200434_gemini-4-argon_dag_engine_lite
# Timestamp: 2026-10-23T20:04:34.794550+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-4-argon (Tier 4)
# Methodology: cleanroom
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 428,474
#   Cached Inbound Tokens:   3,450,111
#   Outbound Tokens:         44,220
#   Total Tokens:            3,922,805
#   Financial Cost ($USD):   $3.0242
#   Wall Clock Duration:     551.63s
#   Step Latencies (s):      []
#   Turn Latencies (s):      []
#   Role Execution Rounds:   coverage: 2, lib: 2, qa: 2, test: 2 (Total: 8)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       20
#   Unit Tests Failed:       0
#   Line Coverage:           95.0%
#   Branch Coverage:         90.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface specification for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

T = TypeVar("T")


@data_type
@dataclass(frozen=True)
class DAGError(Exception):
    """Base exception for all DAG engine errors."""
    message: str


@data_type
@dataclass(frozen=True)
class CycleError(DAGError):
    """Raised when a dependency cycle is detected within the DAG."""
    cycle: Tuple[str, ...]


@data_type
@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    """Raised when a referenced node identifier does not exist in the DAG."""
    node_id: str


@data_type
@dataclass(frozen=True)
class NodeExecutionError(DAGError):
    """Raised when an unhandled exception occurs during node action execution."""
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
# LAST_CLEANED: 2026-10-23T20:08:04Z
# LAST_CHANGED: 2026-10-23T20:08:04Z
# CHANGE: Implement interface types and protocols for dag_engine_lite
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete implementation of the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
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
        # POSTCONDITION: MUST register the node definition into the graph.
        deps_frozenset: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
        definition = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps_frozenset,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()

        # POSTCONDITION: WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id.
        for dep_id in deps_frozenset:
            self._upstream[node_id].add(dep_id)
            if dep_id not in self._downstream:
                self._downstream[dep_id] = set()
            self._downstream[dep_id].add(node_id)

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # POSTCONDITION: WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
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
        # POSTCONDITION: MUST establish a directed dependency edge from upstream_id to downstream_id.
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)
        old_def = self._nodes[downstream_id]
        if upstream_id not in old_def.dependencies:
            self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
                node_id=old_def.node_id,
                action=old_def.action,
                dependencies=frozenset(self._upstream[downstream_id]),
                priority=old_def.priority,
                retries=old_def.retries,
            )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        # POSTCONDITION: MUST remove the node and its incident edges.
        for up_id in list(self._upstream.get(node_id, set())):
            if up_id in self._downstream:
                self._downstream[up_id].discard(node_id)
        for down_id in list(self._downstream.get(node_id, set())):
            if down_id in self._upstream:
                self._upstream[down_id].discard(node_id)
            if down_id in self._nodes:
                down_def = self._nodes[down_id]
                if node_id in down_def.dependencies:
                    self._nodes[down_id] = dag_engine_lite.NodeDefinition(
                        node_id=down_def.node_id,
                        action=down_def.action,
                        dependencies=frozenset(d for d in down_def.dependencies if d != node_id),
                        priority=down_def.priority,
                        retries=down_def.retries,
                    )
        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        # POSTCONDITION: MUST return the NodeDefinition matching node_id.
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        # POSTCONDITION: MUST return all direct upstream dependencies.
        return set(self._upstream[node_id])

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        # POSTCONDITION: WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG.",
                node_id=node_id,
            )
        # POSTCONDITION: MUST return all direct downstream dependents.
        return set(self._downstream[node_id])

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        """Executes depth-first search to detect any directed cycle."""
        visited: Set[str] = set()
        in_stack: Set[str] = set()
        stack: List[str] = []

        def dfs(curr: str) -> Optional[Tuple[str, ...]]:
            visited.add(curr)
            in_stack.add(curr)
            stack.append(curr)
            for nxt in sorted(self._downstream.get(curr, set())):
                if nxt in in_stack:
                    idx = stack.index(nxt)
                    return tuple(stack[idx:] + [nxt])
                if nxt not in visited:
                    res = dfs(nxt)
                    if res is not None:
                        return res
            stack.pop()
            in_stack.remove(curr)
            return None

        for node_id in sorted(self._nodes.keys()):
            if node_id not in visited:
                cycle = dfs(node_id)
                if cycle is not None:
                    return cycle
        return None

    @operation
    @override
    def validate(self) -> None:
        # POSTCONDITION: WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        for node_id in sorted(self._nodes.keys()):
            node_def = self._nodes[node_id]
            deps = set(node_def.dependencies) | self._upstream.get(node_id, set())
            for dep_id in sorted(deps):
                if dep_id not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency node '{dep_id}' referenced by '{node_id}' not found in DAG.",
                        node_id=dep_id,
                    )
        # POSTCONDITION: WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message=f"Cycle detected in DAG: {' -> '.join(cycle)}",
                cycle=cycle,
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        # Compute in-degree counts from _upstream mapping (considering registered nodes).
        in_degree: Dict[str, int] = {
            node_id: sum(1 for u in self._upstream.get(node_id, set()) if u in self._nodes)
            for node_id in self._nodes
        }
        # POSTCONDITION: MUST break ties between concurrent ready nodes using priority descending and name ascending.
        ready: List[str] = [n for n, deg in in_degree.items() if deg == 0]
        ready.sort(key=lambda n: (-self._nodes[n].priority, n))

        order: List[str] = []
        while ready:
            curr = ready.pop(0)
            order.append(curr)
            for down_id in self._downstream.get(curr, set()):
                if down_id in in_degree:
                    in_degree[down_id] -= 1
                    if in_degree[down_id] == 0:
                        ready.append(down_id)
            ready.sort(key=lambda n: (-self._nodes[n].priority, n))

        # POSTCONDITION: WHEN a cycle exists, MUST raise CycleError.
        if len(order) != len(self._nodes):
            cycle = self._find_cycle()
            if cycle is None:  # pragma: no cover (assumption: cycle exists when topological sort fails to visit all nodes)
                remaining = tuple(sorted(set(self._nodes.keys()) - set(order)))
                cycle = remaining
            raise dag_engine_lite.CycleError(
                message=f"Cycle detected in DAG: {' -> '.join(cycle)}",
                cycle=cycle,
            )
        # POSTCONDITION: MUST return a valid topological ordering where every prerequisite precedes its dependents.
        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        return {
            node_id
            for node_id in self._nodes
            if not any(u in self._nodes for u in self._upstream.get(node_id, set()))
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        return {
            node_id
            for node_id in self._nodes
            if not any(d in self._nodes for d in self._downstream.get(node_id, set()))
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        # POSTCONDITION: MUST return the sequence of nodes that forms the longest path through the DAG and its cumulative weight.
        topo_order = self.topological_sort()
        if not topo_order:
            return ([], 0.0)

        durations: Dict[str, float] = {
            node_id: float(estimated_durations[node_id])
            if estimated_durations is not None and node_id in estimated_durations
            else 1.0
            for node_id in self._nodes
        }

        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}

        for node_id in topo_order:
            upstreams = [u for u in self._upstream.get(node_id, set()) if u in self._nodes]
            if not upstreams:
                earliest[node_id] = durations[node_id]
                predecessor[node_id] = None
            else:
                # Select upstream predecessor yielding maximum earliest time (tie-break by priority desc, id asc).
                best_pred = max(
                    upstreams,
                    key=lambda u: (earliest[u], self._nodes[u].priority, u),
                )
                earliest[node_id] = earliest[best_pred] + durations[node_id]
                predecessor[node_id] = best_pred

        terminal_node = max(
            topo_order,
            key=lambda n: (earliest[n], self._nodes[n].priority, n),
        )
        total_weight = earliest[terminal_node]

        path: List[str] = []
        curr: Optional[str] = terminal_node
        while curr is not None:
            path.append(curr)
            curr = predecessor[curr]
        path.reverse()
        return (path, total_weight)


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""
    tier = system

    def __init__(self) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = None
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> dag_engine_lite.DAG:
        """Synchronizes dynamic node state with registered nodes in the active DAG service."""
        dag = get_singleton(dag_engine_lite.DAG)
        self._dag = dag
        current_nodes = dag.all_nodes()
        roots = dag.find_roots()
        # Initialize newly discovered nodes
        for node_id in current_nodes:
            if node_id not in self._states:
                if node_id in roots:
                    self._states[node_id] = dag_engine_lite.NodeState.READY
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
        return dag

    @operation
    @override
    def next_wave(self) -> List[str]:
        dag = self._sync_states()
        # POSTCONDITION: MUST return all nodes currently in READY state whose upstream dependencies are SUCCEEDED.
        ready_nodes: List[str] = []
        for node_id, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                deps = dag.get_dependencies(node_id)
                if all(self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED for d in deps):
                    ready_nodes.append(node_id)
        # POSTCONDITION: MUST order returned nodes by priority descending, then node_id ascending.
        ready_nodes.sort(key=lambda n: (-dag.get_node(n).priority, n))
        return ready_nodes

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        self._sync_states()
        # POSTCONDITION: MUST update the node state to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        dag = self._sync_states()
        # POSTCONDITION: MUST update the node state to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # POSTCONDITION: MUST evaluate downstream dependents and promote newly unblocked nodes to READY.
        if dag.has_node(node_id):
            for down_id in dag.get_dependents(node_id):
                if self._states.get(down_id) == dag_engine_lite.NodeState.PENDING:
                    deps = dag.get_dependencies(down_id)
                    if all(self._states.get(d) == dag_engine_lite.NodeState.SUCCEEDED for d in deps):
                        self._states[down_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        dag = self._sync_states()
        # POSTCONDITION: MUST update the node state to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            # POSTCONDITION: WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING/non-terminal nodes to CANCELLED.
            for other_id, st in list(self._states.items()):
                if st not in terminal_states:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy == dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # POSTCONDITION: WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
            queue: List[str] = list(dag.get_dependents(node_id)) if dag.has_node(node_id) else []
            visited: Set[str] = set(queue)
            while queue:
                curr = queue.pop(0)
                if self._states.get(curr) not in terminal_states:
                    self._states[curr] = dag_engine_lite.NodeState.SKIPPED
                if dag.has_node(curr):
                    for nxt in dag.get_dependents(curr):
                        if nxt not in visited:
                            visited.add(nxt)
                            queue.append(nxt)
        # POSTCONDITION: WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution.

    @operation
    @override
    def is_finished(self) -> bool:
        dag = self._sync_states()
        all_node_ids = dag.all_nodes()
        # POSTCONDITION: WHEN the DAG contains no nodes, MUST return True.
        if not all_node_ids:
            return True
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        # POSTCONDITION: WHEN all nodes in the DAG have reached terminal states, MUST return True; otherwise False.
        return all(self._states.get(n) in terminal_states for n in all_node_ids)

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        if node_id not in self._states:
            self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        return dict(self._states)


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""
    tier = system

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
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._dag = dag
        self._scheduler = scheduler

        # Validate DAG consistency and acyclicity before execution.
        dag.validate()

        run_start = time.perf_counter()
        self._results = {}
        halted = False

        # POSTCONDITION: MUST execute ready waves sequentially.
        while not scheduler.is_finished() and not halted:
            wave = scheduler.next_wave()
            if not wave:
                break

            for node_id in wave:
                if halted:
                    break
                node_def = dag.get_node(node_id)
                scheduler.mark_running(node_id)

                node_start = time.perf_counter()
                attempts = 0
                max_retries = max(0, node_def.retries)
                succeeded = False
                result_val: Any = None
                caught_exc: Optional[Exception] = None

                # POSTCONDITION: MUST execute retries up to the configured retry count for failed node actions.
                while True:
                    try:
                        result_val = node_def.action()
                        succeeded = True
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        caught_exc = exc
                        if attempts < max_retries:
                            attempts += 1
                        else:
                            break

                duration = time.perf_counter() - node_start
                if succeeded:
                    scheduler.mark_succeeded(node_id)
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=result_val,
                        error=None,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                else:
                    # POSTCONDITION: MUST apply the specified failure_policy to the scheduler upon node failure.
                    scheduler.mark_failed(node_id, failure_policy=failure_policy)
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=caught_exc,
                        duration_seconds=duration,
                        retries_attempted=attempts,
                    )
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True

        wall_clock = time.perf_counter() - run_start
        all_states = scheduler.get_all_states()

        # Populate _results with default unexecuted NodeResult records for terminal skipped or cancelled (or unexecuted) nodes.
        for node_id, st in all_states.items():
            if node_id not in self._results:
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=st,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        # Compute critical path using _dag.compute_critical_path().
        critical_path_list, _ = dag.compute_critical_path()

        succeeded_nodes = tuple(
            nid for nid, st in all_states.items() if st == dag_engine_lite.NodeState.SUCCEEDED
        )
        failed_nodes = tuple(
            nid for nid, st in all_states.items() if st == dag_engine_lite.NodeState.FAILED
        )
        skipped_nodes = tuple(
            nid for nid, st in all_states.items() if st == dag_engine_lite.NodeState.SKIPPED
        )
        cancelled_nodes = tuple(
            nid for nid, st in all_states.items() if st == dag_engine_lite.NodeState.CANCELLED
        )

        # POSTCONDITION: MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(all_states),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(critical_path_list),
            results=dict(self._results),
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

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-23T20:13:43Z
# LAST_CHANGED: 2026-10-23T20:11:31Z
# CHANGE: Remove unreachable branches in _find_cycle and _sync_states
# COVERAGE_AUDIT: 2026-10-23T20:13:43Z
# QA_AUDIT: 2026-10-23T20:13:04Z
# --- END CLEANROOM METADATA ---
