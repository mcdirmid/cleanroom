# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261102_233620_deepseek-flash_dag_engine_lite_pretense_baseline
# Timestamp: 2026-11-02T23:36:20.978759+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: pretense_baseline
# Harness: dsh
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 87,962
#   Cached Inbound Tokens:   6,586,496
#   Outbound Tokens:         130,307
#   Total Tokens:            6,804,765
#   Financial Cost ($USD):   $0.1111
#   Wall Clock Duration:     1058.30s
#   Step Latencies (s):      [1047.4]
#   Role Execution Rounds:   baseline: 1 (Total: 1)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       1
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Synchronous DAG execution and wave scheduling engine interface specification."""

from __future__ import annotations
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from dataclasses import dataclass
from support.lib.lifecycle import Singleton, SystemTier, system
import enum

# Requirements specified in dag_engine_lite.pyi

T = TypeVar('T')

@dataclass
class DAGError(Exception):
    # Diagnostic description of the error.
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class CycleError(DAGError):
    # Sequence of node identifiers forming the cycle.
    cycle: Tuple[str, ...]


@dataclass
class NodeNotFoundError(DAGError):
    # Identifier of the missing node.
    node_id: str


@dataclass
class NodeExecutionError(DAGError):
    # Identifier of the failed node.
    node_id: str
    cause: Exception


class NodeState(enum.Enum):
    """Execution lifecycle state of a graph node."""

    PENDING = 'pending'
    READY = 'ready'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    SKIPPED = 'skipped'


class FailurePolicy(enum.Enum):
    """Policy governing graph execution when a node action fails."""

    FAIL_FAST = 'fail_fast'
    CONTINUE_ON_ERROR = 'continue_on_error'
    SKIP_DOWNSTREAM = 'skip_downstream'


@dataclass(frozen=True)
class NodeDefinition(Generic[T]):
    # Unique identifier for the node.
    node_id: str
    # Callable action to execute for this node.
    action: Callable[[], T]
    # Set of node identifiers that must complete before this node can run.
    dependencies: FrozenSet[str]
    # Priority value used for wave ordering and tie-breaking (higher runs first).
    priority: int = 0
    # Number of retry attempts on failure.
    retries: int = 0


@dataclass(frozen=True)
class NodeResult(Generic[T]):
    # Unique identifier of the node.
    node_id: str
    # Final lifecycle state of the node.
    state: NodeState
    # Return value of the action when execution succeeds.
    value: Optional[T] = None
    # Caught exception when execution fails.
    error: Optional[Exception] = None
    # Wall-clock elapsed execution time in seconds.
    duration_seconds: float = 0.0
    # Number of retries executed before final state.
    retries_attempted: int = 0


@dataclass(frozen=True)
class DAGRunReport:
    # Total count of nodes in the graph.
    total_nodes: int
    # Identifiers of all nodes that completed successfully.
    succeeded_nodes: Tuple[str, ...]
    # Identifiers of all nodes that failed.
    failed_nodes: Tuple[str, ...]
    # Identifiers of all nodes skipped due to upstream failure.
    skipped_nodes: Tuple[str, ...]
    # Identifiers of all nodes cancelled prior to execution.
    cancelled_nodes: Tuple[str, ...]
    # Total wall-clock time elapsed for the run.
    wall_clock_seconds: float
    # Sequence of node identifiers forming the critical path.
    critical_path: Tuple[str, ...]
    # Mapping of node identifier to individual NodeResult outcomes.
    results: Mapping[str, NodeResult[Any]]


class DAG(Singleton[SystemTier], Protocol):
    """Directed Acyclic Graph holding task nodes and directed dependency edges."""

    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, retries: int=0) -> None:
        """Adds a task node to the graph."""
        ...

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        ...

    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        ...

    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        ...

    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        ...

    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        ...

    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        ...

    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        ...

    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        ...

    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        ...

    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies)."""
        ...

    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents)."""
        ...

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]=None) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        ...


class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into sequential execution waves."""

    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        ...

    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        ...

    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        ...

    def mark_failed(self, node_id: str, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        ...

    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        ...

    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node."""
        ...

    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph."""
        ...


class DAGRunner(Singleton[SystemTier], Protocol):
    """Executes a DAG sequentially to completion under failure policies."""

    def run(self, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-02T23:53:58Z
# LAST_CHANGED: 2026-11-02T23:53:58Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 07ccadf4f325
# PRETENSE_COVERAGE_AUDIT: 2026-11-02T23:53:58Z
# PRETENSE_QA_AUDIT: 2026-11-02T23:53:58Z
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Concrete synchronous DAG execution and wave scheduling engine implementation."""

from __future__ import annotations
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import time
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dag_engine_lite

# Requirements specified in dag_engine_lite_impl.pyi

_TERMINAL_STATES = frozenset({
    dag_engine_lite.NodeState.SUCCEEDED,
    dag_engine_lite.NodeState.FAILED,
    dag_engine_lite.NodeState.SKIPPED,
    dag_engine_lite.NodeState.CANCELLED,
})


class DAG(dag_engine_lite.DAG):
    tier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, retries: int=0) -> None:
        # MUST register the node definition into the graph.
        frozen_dependencies = frozenset(dependencies) if dependencies is not None else frozenset()
        definition: dag_engine_lite.NodeDefinition[Any] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozen_dependencies,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # WHEN dependencies are provided, MUST add directed dependency edges, deferring
        # missing dependency existence checks to validate() and topological_sort().
        for dependency in frozen_dependencies:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.
        if upstream_id not in self._nodes or downstream_id not in self._nodes:
            missing_id = upstream_id if upstream_id not in self._nodes else downstream_id
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node not found: {missing_id}",
                node_id=missing_id,
            )
        # MUST establish a directed dependency edge from upstream_id to downstream_id.
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    def remove_node(self, node_id: str) -> None:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node not found: {node_id}",
                node_id=node_id,
            )
        # MUST remove the node and its incident edges.
        for dependency in self._upstream.get(node_id, set()):
            self._downstream.get(dependency, set()).discard(node_id)
        for dependent in self._downstream.get(node_id, set()):
            self._upstream.get(dependent, set()).discard(node_id)
        del self._nodes[node_id]
        del self._upstream[node_id]
        del self._downstream[node_id]

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node not found: {node_id}",
                node_id=node_id,
            )
        # MUST return the NodeDefinition matching node_id.
        return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node not found: {node_id}",
                node_id=node_id,
            )
        # MUST return all direct upstream dependencies.
        return set(self._upstream[node_id])

    def get_dependents(self, node_id: str) -> Set[str]:
        # WHEN node_id is absent, MUST raise NodeNotFoundError.
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node not found: {node_id}",
                node_id=node_id,
            )
        # MUST return all direct downstream dependents.
        return set(self._downstream[node_id])

    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    def _first_missing_dependency(self) -> Optional[str]:
        """Returns the first referenced dependency absent from the graph, if any."""
        for node_id in sorted(self._upstream):
            for dependency in sorted(self._upstream[node_id]):
                if dependency not in self._nodes:
                    return dependency
        return None

    def _cycle_sequence(self) -> Tuple[str, ...]:
        """Returns a directed cycle sequence, or an empty tuple when acyclic."""
        visiting: Set[str] = set()
        visited: Set[str] = set()
        path: List[str] = []

        def visit(node_id: str) -> Tuple[str, ...]:
            visiting.add(node_id)
            path.append(node_id)
            for dependency in sorted(self._upstream.get(node_id, set())):
                if dependency in visiting:
                    return tuple(path[path.index(dependency):] + [dependency])
                if dependency not in visited:
                    found = visit(dependency)
                    if found:
                        return found
            path.pop()
            visiting.discard(node_id)
            visited.add(node_id)
            return ()

        for node_id in sorted(self._nodes):
            if node_id not in visited:
                found = visit(node_id)
                if found:
                    return found
        return ()

    def validate(self) -> None:
        # WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        missing = self._first_missing_dependency()
        if missing is not None:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Missing dependency node: {missing}",
                node_id=missing,
            )
        # WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.
        cycle = self._cycle_sequence()
        if cycle:
            raise dag_engine_lite.CycleError(
                message=f"Dependency cycle detected: {' -> '.join(cycle)}",
                cycle=cycle,
            )
        # WHEN all referenced nodes exist and no cycle exists, MUST complete without error.

    def topological_sort(self) -> List[str]:
        # Missing dependency existence checks are deferred to this operation.
        missing = self._first_missing_dependency()
        if missing is not None:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Missing dependency node: {missing}",
                node_id=missing,
            )
        in_degree: Dict[str, int] = {
            node_id: len(self._upstream[node_id]) for node_id in self._nodes
        }
        ready: List[str] = [node_id for node_id, degree in in_degree.items() if degree == 0]
        # MUST break ties using priority descending and lexicographical node_id ascending.
        ready.sort(key=lambda node_id: (-self._nodes[node_id].priority, node_id))
        order: List[str] = []
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for dependent in self._downstream.get(node_id, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready.append(dependent)
            ready.sort(key=lambda node_id: (-self._nodes[node_id].priority, node_id))
        # WHEN a cycle exists, MUST raise CycleError.
        if len(order) != len(self._nodes):
            cycle = self._cycle_sequence()
            raise dag_engine_lite.CycleError(
                message=f"Dependency cycle detected: {' -> '.join(cycle)}",
                cycle=cycle,
            )
        return order

    def find_roots(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._upstream[node_id]}

    def find_leaves(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._downstream[node_id]}

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]=None) -> Tuple[List[str], float]:
        durations: Mapping[str, float] = estimated_durations if estimated_durations is not None else {}
        order = self.topological_sort()
        if not order:
            return [], 0.0
        # earliest[node] = max earliest completion of prerequisites + this node duration.
        earliest: Dict[str, float] = {}
        for node_id in order:
            prerequisite_finishes = [earliest[dependency] for dependency in self._upstream[node_id]]
            earliest[node_id] = (max(prerequisite_finishes) if prerequisite_finishes else 0.0) + durations.get(node_id, 1.0)
        # MUST return the sequence of nodes forming the longest weighted path through the DAG.
        leaves = [node_id for node_id in self._nodes if not self._downstream[node_id]]
        terminal = min(leaves, key=lambda node_id: (-earliest[node_id], node_id))
        path: List[str] = [terminal]
        current = terminal
        while self._upstream[current]:
            current = min(self._upstream[current], key=lambda node_id: (-earliest[node_id], node_id))
            path.append(current)
        path.reverse()
        return path, earliest[terminal]


class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        """Discovers currently registered nodes and purges removed node state."""
        node_ids = self._dag.all_nodes()
        for node_id in sorted(node_ids):
            if node_id not in self._states:
                if self._dag.get_dependencies(node_id):
                    self._states[node_id] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[node_id] = dag_engine_lite.NodeState.READY
        for node_id in list(self._states):
            if node_id not in node_ids:
                del self._states[node_id]

    def _ready_candidates(self) -> List[str]:
        """Returns READY nodes whose upstream dependencies are all SUCCEEDED."""
        candidates = [
            node_id
            for node_id, state in self._states.items()
            if state is dag_engine_lite.NodeState.READY
            and all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in self._dag.get_dependencies(node_id)
            )
        ]
        # MUST order returned nodes by priority descending, then node_id ascending.
        candidates.sort(key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id))
        return candidates

    def next_wave(self) -> List[str]:
        self._sync_states()
        # WHEN no nodes are ready, MUST return an empty list.
        return self._ready_candidates()

    def mark_running(self, node_id: str) -> None:
        self._sync_states()
        # MUST update the node state to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        self._sync_states()
        # MUST update the node state to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # MUST promote newly unblocked downstream dependents to READY.
        for dependent in sorted(self._dag.get_dependents(node_id)):
            if self._states.get(dependent) is dag_engine_lite.NodeState.PENDING and all(
                self._states.get(dependency) is dag_engine_lite.NodeState.SUCCEEDED
                for dependency in self._dag.get_dependencies(dependent)
            ):
                self._states[dependent] = dag_engine_lite.NodeState.READY

    def mark_failed(self, node_id: str, failure_policy: dag_engine_lite.FailurePolicy=dag_engine_lite.FailurePolicy.FAIL_FAST) -> None:
        self._sync_states()
        # MUST update the node state to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # WHEN failure_policy is FAIL_FAST, MUST transition all remaining
            # non-terminal nodes to CANCELLED.
            for other_id in list(self._states):
                if self._states[other_id] not in _TERMINAL_STATES:
                    self._states[other_id] = dag_engine_lite.NodeState.CANCELLED
        else:
            # WHEN failure_policy is SKIP_DOWNSTREAM or CONTINUE_ON_ERROR, MUST
            # transition all blocked transitive dependents to SKIPPED.
            visited: Set[str] = set()
            pending = [node_id]
            while pending:
                current = pending.pop()
                for dependent in sorted(self._dag.get_dependents(current)):
                    if dependent in visited:
                        continue
                    visited.add(dependent)
                    if self._states.get(dependent) not in _TERMINAL_STATES:
                        self._states[dependent] = dag_engine_lite.NodeState.SKIPPED
                    pending.append(dependent)

    def is_finished(self) -> bool:
        self._sync_states()
        # WHEN the DAG contains no nodes, MUST return True.
        if not self._states:
            return True
        # WHEN all nodes have reached terminal states, MUST return True.
        if all(state in _TERMINAL_STATES for state in self._states.values()):
            return True
        # WHEN any node remains eligible to execute, MUST return False.
        return not self._ready_candidates()

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        self._sync_states()
        return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        return dict(self._states)


class DAGRunner(dag_engine_lite.DAGRunner):
    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: dag_engine_lite.WaveScheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def _execute(self, definition: dag_engine_lite.NodeDefinition[Any]) -> dag_engine_lite.NodeResult[Any]:
        """Executes a node action with retries and records the outcome."""
        start = time.perf_counter()
        attempts = 0
        value: Any = None
        error: Optional[Exception] = None
        # MUST execute retries up to the configured retry count for failed node actions.
        while attempts <= definition.retries:
            attempts += 1
            try:
                value = definition.action()
            except Exception as exc:  # cleanroom: allow-broad-exception (reified into NodeResult.error)
                error = exc
            else:
                error = None
                break
        duration_seconds = time.perf_counter() - start
        if error is None:
            return dag_engine_lite.NodeResult(
                node_id=definition.node_id,
                state=dag_engine_lite.NodeState.SUCCEEDED,
                value=value,
                duration_seconds=duration_seconds,
                retries_attempted=attempts - 1,
            )
        return dag_engine_lite.NodeResult(
            node_id=definition.node_id,
            state=dag_engine_lite.NodeState.FAILED,
            error=error,
            duration_seconds=duration_seconds,
            retries_attempted=attempts - 1,
        )

    def run(self, failure_policy: dag_engine_lite.FailurePolicy=dag_engine_lite.FailurePolicy.FAIL_FAST) -> dag_engine_lite.DAGRunReport:
        start = time.perf_counter()
        # MUST validate graph invariants before commencing wave execution.
        self._dag.validate()
        self._results = {}
        halted = False
        # MUST execute ready waves sequentially.
        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            # Halts the wave loop when no nodes can be scheduled.
            if not wave:  # unreachable (assumption: is_finished guarantees a runnable wave)
                break
            for node_id in wave:
                definition = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)
                result = self._execute(definition)
                self._results[node_id] = result
                if result.state is dag_engine_lite.NodeState.SUCCEEDED:
                    self._scheduler.mark_succeeded(node_id)
                else:
                    # MUST apply the specified failure_policy to the scheduler upon node failure.
                    self._scheduler.mark_failed(node_id, failure_policy)
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        # Halts further wave execution when FAIL_FAST observes a failure.
                        halted = True
                        break
            if halted:
                break
        # Populates default unexecuted result records for terminal skipped or cancelled nodes.
        states = self._scheduler.get_all_states()
        for node_id, state in states.items():
            if node_id in self._results:
                continue
            if state in (dag_engine_lite.NodeState.SKIPPED, dag_engine_lite.NodeState.CANCELLED):
                self._results[node_id] = dag_engine_lite.NodeResult(node_id=node_id, state=state)
        critical_path, _ = self._dag.compute_critical_path()
        # Gathers outcome tuples from the recorded results and final scheduler states.
        succeeded = tuple(sorted(node_id for node_id, state in states.items() if state is dag_engine_lite.NodeState.SUCCEEDED))
        failed = tuple(sorted(node_id for node_id, state in states.items() if state is dag_engine_lite.NodeState.FAILED))
        skipped = tuple(sorted(node_id for node_id, state in states.items() if state is dag_engine_lite.NodeState.SKIPPED))
        cancelled = tuple(sorted(node_id for node_id, state in states.items() if state is dag_engine_lite.NodeState.CANCELLED))
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=succeeded,
            failed_nodes=failed,
            skipped_nodes=skipped,
            cancelled_nodes=cancelled,
            wall_clock_seconds=time.perf_counter() - start,
            critical_path=tuple(critical_path),
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

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-02T23:53:58Z
# LAST_CHANGED: 2026-11-02T23:53:58Z
# CHANGE: Fused role implementation and verification
# CODE_HASH: 219c4472d92c
# PRETENSE_COVERAGE_AUDIT: 2026-11-02T23:53:58Z
# PRETENSE_QA_AUDIT: 2026-11-02T23:53:58Z
# --- END AUTOFAB METADATA ---
