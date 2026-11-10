# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261109_175929_deepseek-flash_dag_engine_lite_combined
# Timestamp: 2026-11-09T17:59:29.853268+00:00
# Benchmark Task: dag_engine_lite
# Model: deepseek-flash (Tier 2)
# Methodology: combined
# Harness: dsh
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 460,538
#   Cached Inbound Tokens:   32,526,848
#   Outbound Tokens:         457,607
#   Total Tokens:            33,444,993
#   Financial Cost ($USD):   $0.4412
#   Wall Clock Duration:     2042.17s
#   Step Latencies (s):      [268.8, 383.8, 20.3, 301.8, 767.9, 105.0, 102.8, 12.3, 22.6, 127.8, 150.9, 76.8, 105.3, 20.4, 225.8, 97.3, 74.2, 10.0, 109.7, 22.8, 135.7, 20.3, 155.7, 125.3, 51.1, 74.1, 20.4, 73.8, 74.0, 20.4, 20.3]
#   Role Execution Rounds:   coverage: 4, lib: 3, pretense: 6, pretense_coverage: 4, pretense_qa: 6, qa: 4, test: 4 (Total: 31)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       50
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Library interface for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Set, Tuple, TypeVar

from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier

# Requirements specified in dag_engine_lite.pyi

T = TypeVar('T')


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


@singleton_type('system')
class DAG(Singleton[SystemTier], Protocol):
    """Directed Acyclic Graph holding task nodes and directed dependency edges."""

    @operation
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]], priority: int, retries: int) -> None:
        """Adds a task node to the graph.

        PRECONDITIONS:
        - WHEN node_id is already registered, MUST raise DuplicateNodeError.

        POSTCONDITIONS:
        - MUST register the node definition into the graph.
        - WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id.
        - MUST defer missing dependency existence checks to validate() and topological_sort().
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        PRECONDITIONS:
        - WHEN either identifier is absent, MUST raise NodeNotFoundError.

        POSTCONDITIONS:
        - MUST establish a directed dependency edge from upstream_id to downstream_id.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        PRECONDITIONS:
        - WHEN node_id is absent, MUST raise NodeNotFoundError.

        POSTCONDITIONS:
        - MUST remove the node and its incident edges.
        - MUST purge the node identifier from wave scheduler state tracking.
        """
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        PRECONDITIONS:
        - WHEN node_id is absent, MUST raise NodeNotFoundError.

        POSTCONDITIONS:
        - MUST return the NodeDefinition matching node_id.
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        PRECONDITIONS:
        - WHEN node_id is absent, MUST raise NodeNotFoundError.

        POSTCONDITIONS:
        - MUST return all direct upstream dependencies.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        PRECONDITIONS:
        - WHEN node_id is absent, MUST raise NodeNotFoundError.

        POSTCONDITIONS:
        - MUST return all direct downstream dependents.
        """
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        ...

    @operation
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity.

        PRECONDITIONS:
        - WHEN a referenced dependency is missing, MUST raise NodeNotFoundError.
        - WHEN the graph contains a directed cycle, MUST raise CycleError.

        POSTCONDITIONS:
        - WHEN all referenced nodes exist and no cycle exists, MUST complete without error.
        """
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        Tie-breaking between independent nodes is resolved first by priority (descending),
        then alphabetically by node_id (ascending).

        POSTCONDITIONS:
        - MUST return a valid topological ordering where every prerequisite precedes its dependents.
        - MUST break ties between concurrent ready nodes using priority descending and lexicographical node_id ascending.
        """
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
    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph.

        POSTCONDITIONS:
        - MUST return the sequence of nodes that forms the longest path through the DAG.
        - MUST return the cumulative weight of that path.
        """
        ...


@singleton_type('system')
class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into sequential execution waves."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        POSTCONDITIONS:
        - MUST return all nodes currently in READY state whose upstream dependencies are SUCCEEDED.
        - MUST order returned nodes by priority descending, then node_id ascending.
        - WHEN no nodes are ready, MUST return an empty list.
        """
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
    def mark_failed(self, node_id: str, failure_policy: FailurePolicy) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node.

        PRECONDITIONS:
        - WHEN node_id is not registered in the scheduled DAG, MUST raise NodeNotFoundError.
        """
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph."""
        ...


@singleton_type('system')
class DAGRunner(Singleton[SystemTier], Protocol):
    """Executes a DAG sequentially to completion under failure policies."""

    @operation
    def run(self, failure_policy: FailurePolicy) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure.

        PRECONDITIONS:
        - WHEN a referenced dependency is missing, MUST raise NodeNotFoundError.
        - WHEN the graph contains a directed cycle, MUST raise CycleError.

        POSTCONDITIONS:
        - MUST validate graph invariants before commencing wave execution.
        - MUST execute ready waves sequentially.
        - MUST execute retries up to the configured retry count for failed node actions.
        - MUST apply the specified failure_policy to the scheduler upon node failure.
        - MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-09T18:06:07Z
# LAST_CHANGED: 2026-11-09T18:06:07Z
# CHANGE: Implemented the library interface: concrete exception dataclasses (non-frozen DAGError/CycleError/NodeNotFoundError/DuplicateNodeError/NodeExecutionError with __str__ delegating to message so Python can assign __traceback__), frozen data types (NodeDefinition, NodeResult, DAGRunReport), NodeState/FailurePolicy enums, and @singleton_type service protocols (DAG, WaveScheduler, DAGRunner) with contract docstrings mirroring low/dag_engine_lite.pyi.
# --- END AUTOFAB METADATA ---


# === File: dag_engine_lite_impl.py ===
from __future__ import annotations
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dag_engine_lite

# Requirements specified in dag_engine_lite_impl.pyi

_TERMINAL_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
    {
        dag_engine_lite.NodeState.SUCCEEDED,
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)

_BLOCKING_STATES: FrozenSet[dag_engine_lite.NodeState] = frozenset(
    {
        dag_engine_lite.NodeState.FAILED,
        dag_engine_lite.NodeState.SKIPPED,
        dag_engine_lite.NodeState.CANCELLED,
    }
)


def _is_terminal(state: Optional[dag_engine_lite.NodeState]) -> bool:
    """Reports whether a node state is terminal (SUCCEEDED, FAILED, SKIPPED, CANCELLED)."""
    return state is not None and state in _TERMINAL_STATES


@singleton_type('system')
class DAG(dag_engine_lite.DAG):
    tier = system

    def __init__(self) -> None:
        # Backing state: immutable definitions plus downstream/upstream adjacency.
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]], priority: int, retries: int) -> None:
        # PRECONDITION: node_id must not already be registered (raises DuplicateNodeError).
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                f"Node '{node_id}' is already registered in the DAG",
                node_id,
            )
        declared = frozenset(dependencies) if dependencies is not None else frozenset()
        # POSTCONDITION: register the immutable node definition.
        definition: dag_engine_lite.NodeDefinition[Any] = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=declared,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = definition
        self._upstream.setdefault(node_id, set())
        self._downstream.setdefault(node_id, set())
        # POSTCONDITION: WHEN dependencies are provided, add directed dependency edges.
        # Existence checks are deferred to validate() and topological_sort().
        for dependency in declared:
            self._upstream[node_id].add(dependency)
            self._downstream.setdefault(dependency, set()).add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # PRECONDITION: both endpoints must exist (raises NodeNotFoundError).
        for endpoint in (upstream_id, downstream_id):
            if endpoint not in self._nodes:
                raise dag_engine_lite.NodeNotFoundError(
                    f"Node '{endpoint}' is not registered in the DAG",
                    endpoint,
                )
        # POSTCONDITION: establish the directed downstream dependency edge.
        self._upstream.setdefault(downstream_id, set()).add(upstream_id)
        self._downstream.setdefault(upstream_id, set()).add(downstream_id)

    def remove_node(self, node_id: str) -> None:
        # PRECONDITION: node_id must exist (raises NodeNotFoundError).
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG",
                node_id,
            )
        # POSTCONDITION: purge the node and all incident edges.
        for upstream in tuple(self._upstream.get(node_id, ())):
            self._downstream.get(upstream, set()).discard(node_id)
        for downstream in tuple(self._downstream.get(node_id, ())):
            self._upstream.get(downstream, set()).discard(node_id)
        self._nodes.pop(node_id, None)
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # PRECONDITION: node_id must exist (raises NodeNotFoundError).
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG",
                node_id,
            )
        # POSTCONDITION: return the registered definition.
        return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        # PRECONDITION: node_id must exist (raises NodeNotFoundError).
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG",
                node_id,
            )
        # POSTCONDITION: return all direct upstream dependencies.
        return set(self._upstream.get(node_id, ()))

    def get_dependents(self, node_id: str) -> Set[str]:
        # PRECONDITION: node_id must exist (raises NodeNotFoundError).
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the DAG",
                node_id,
            )
        # POSTCONDITION: return all direct downstream dependents.
        return set(self._downstream.get(node_id, ()))

    def all_nodes(self) -> Set[str]:
        return set(self._nodes.keys())

    def validate(self) -> None:
        # PRECONDITION: every referenced dependency must exist (raises NodeNotFoundError).
        self._check_dependencies()
        # PRECONDITION: the graph must be acyclic (raises CycleError).
        cycle = self._find_cycle()
        if cycle:
            raise dag_engine_lite.CycleError(
                'Dependency cycle detected: ' + ' -> '.join(cycle),
                cycle,
            )
        # POSTCONDITION: complete without error when all nodes exist and the graph is acyclic.

    def topological_sort(self) -> List[str]:
        # Missing dependencies deferred from add_node are reported here (raises NodeNotFoundError).
        self._check_dependencies()
        indegree: Dict[str, int] = {
            node_id: len(self._upstream.get(node_id, ())) for node_id in self._nodes
        }
        ready: List[str] = [node_id for node_id in self._nodes if indegree[node_id] == 0]
        # POSTCONDITION: tie-break by priority descending, then node_id ascending.
        ready.sort(key=self._ordering_key)
        order: List[str] = []
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for dependent in sorted(self._downstream.get(node_id, ())):
                if dependent not in indegree:  # pragma: no cover (assumption: adjacency_invariants - downstream members are registered nodes)
                    continue
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
                    ready.sort(key=self._ordering_key)
        if len(order) != len(self._nodes):
            # PRECONDITION: acyclic graph (raises CycleError). A Kahn shortfall necessarily
            # means a directed cycle exists, so _find_cycle() resolves its node sequence.
            cycle = self._find_cycle()
            raise dag_engine_lite.CycleError(
                'Dependency cycle detected: ' + ' -> '.join(cycle),
                cycle,
            )
        # POSTCONDITION: every prerequisite precedes its dependents in the returned order.
        return order

    def find_roots(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._upstream.get(node_id)}

    def find_leaves(self) -> Set[str]:
        return {node_id for node_id in self._nodes if not self._downstream.get(node_id)}

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]) -> Tuple[List[str], float]:
        order = self.topological_sort()
        if not order:
            return ([], 0.0)
        # POSTCONDITION: cumulative weight of the longest weighted dependency path.
        durations: Dict[str, float] = {
            node_id: (
                estimated_durations.get(node_id, 1.0)
                if estimated_durations is not None
                else 1.0
            )
            for node_id in order
        }
        earliest: Dict[str, float] = {}
        for node_id in order:
            upstream = [p for p in self._upstream.get(node_id, ()) if p in earliest]
            earliest[node_id] = (
                max(earliest[p] for p in upstream) if upstream else 0.0
            ) + durations[node_id]
        # Identify the terminal (leaf) node with the maximum completion time. A non-empty
        # acyclic graph always has at least one leaf, so the candidate list is never empty.
        leaf_nodes = [node_id for node_id in order if not self._downstream.get(node_id)]
        best = leaf_nodes[0]
        for node_id in leaf_nodes[1:]:
            if earliest[node_id] > earliest[best]:
                best = node_id
        # POSTCONDITION: backtrack the longest path selecting the predecessor with maximum earliest time.
        path: List[str] = []
        current = best
        while True:
            path.append(current)
            candidates = [p for p in self._upstream.get(current, ()) if p in earliest]
            if not candidates:
                break
            chosen = candidates[0]
            for predecessor in candidates[1:]:
                if earliest[predecessor] > earliest[chosen] or (
                    earliest[predecessor] == earliest[chosen] and predecessor < chosen
                ):
                    chosen = predecessor
            current = chosen
        path.reverse()
        return (path, earliest[best])

    def _ordering_key(self, node_id: str) -> Tuple[int, str]:
        return (-self._nodes[node_id].priority, node_id)

    def _check_dependencies(self) -> None:
        # The adjacency sets are authoritative: add_node records declared dependencies
        # (which may reference nodes not yet registered) while remove_node purges edges.
        for node_id in sorted(self._nodes):
            for dependency in sorted(self._upstream.get(node_id, ())):
                if dependency not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        f"Node '{node_id}' depends on missing node '{dependency}'",
                        dependency,
                    )

    def _find_cycle(self) -> Tuple[str, ...]:
        # Returns the node sequence of a directed cycle, or an empty tuple when acyclic.
        color: Dict[str, int] = {}
        stack: List[str] = []
        positions: Dict[str, int] = {}

        def visit(node_id: str) -> Optional[Tuple[str, ...]]:
            color[node_id] = 1
            positions[node_id] = len(stack)
            stack.append(node_id)
            for dependent in sorted(self._downstream.get(node_id, ())):
                if dependent not in self._nodes:  # pragma: no cover (assumption: registered_downstream_members - dependents are registered nodes)
                    continue
                state = color.get(dependent, 0)
                if state == 1:
                    return tuple(stack[positions[dependent]:]) + (dependent,)
                if state == 0:
                    cycle = visit(dependent)
                    if cycle is not None:
                        return cycle
            stack.pop()
            positions.pop(node_id, None)
            color[node_id] = 2
            return None

        for node_id in sorted(self._nodes):
            if color.get(node_id, 0) == 0:
                cycle = visit(node_id)
                if cycle is not None:
                    return cycle
        return ()


@singleton_type('system')
class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = system

    def __init__(self) -> None:
        # Collaborator resolved on demand from the ambient lifecycle registry.
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def next_wave(self) -> List[str]:
        self._sync_states()
        # POSTCONDITION: promote PENDING nodes whose upstream dependencies are all SUCCEEDED.
        for node_id in sorted(self._states):
            if (
                self._states[node_id] is dag_engine_lite.NodeState.PENDING
                and self._dependencies_satisfied(node_id)
            ):
                self._states[node_id] = dag_engine_lite.NodeState.READY
        # POSTCONDITION: return all READY nodes whose dependencies are satisfied.
        wave = [
            node_id
            for node_id in self._states
            if self._states[node_id] is dag_engine_lite.NodeState.READY
            and self._dependencies_satisfied(node_id)
        ]
        # POSTCONDITION: order by priority descending, then node_id ascending.
        wave.sort(key=lambda node_id: (-self._dag.get_node(node_id).priority, node_id))
        return wave

    def mark_running(self, node_id: str) -> None:
        self._sync_states()
        # POSTCONDITION: transition the node to RUNNING.
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        self._sync_states()
        # POSTCONDITION: transition the node to SUCCEEDED.
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        # POSTCONDITION: promote newly unblocked dependents to READY.
        for dependent in sorted(self._dag.get_dependents(node_id)):
            if (
                self._states.get(dependent) is dag_engine_lite.NodeState.PENDING
                and self._dependencies_satisfied(dependent)
            ):
                self._states[dependent] = dag_engine_lite.NodeState.READY

    def mark_failed(self, node_id: str, failure_policy: dag_engine_lite.FailurePolicy) -> None:
        self._sync_states()
        # POSTCONDITION: transition the node to FAILED.
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
            # POSTCONDITION: WHEN FAIL_FAST, cancel all remaining non-terminal nodes.
            for other in list(self._states):
                if not _is_terminal(self._states[other]):
                    self._states[other] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM:
            # POSTCONDITION: WHEN SKIP_DOWNSTREAM, skip all transitive dependents.
            for dependent in self._transitive_dependents(node_id):
                if not _is_terminal(self._states.get(dependent)):
                    self._states[dependent] = dag_engine_lite.NodeState.SKIPPED
        else:
            # POSTCONDITION: WHEN CONTINUE_ON_ERROR, keep unblocked independent nodes
            # eligible and skip only dependents blocked by a failed ancestor.
            for other in sorted(self._states):
                if other == node_id:
                    continue
                if _is_terminal(self._states[other]):
                    continue
                if self._has_blocking_ancestor(other):
                    self._states[other] = dag_engine_lite.NodeState.SKIPPED

    def is_finished(self) -> bool:
        self._sync_states()
        # POSTCONDITION: WHEN the DAG contains no nodes, return True.
        if not self._states:
            return True
        remaining = [
            node_id
            for node_id in sorted(self._states)
            if not _is_terminal(self._states[node_id])
        ]
        # POSTCONDITION: WHEN all nodes are terminal, return True.
        if not remaining:
            return True
        # POSTCONDITION: WHEN no ready nodes remain and unexecuted nodes are blocked
        # by failed dependencies, return True.
        if not self.next_wave() and all(
            self._has_blocking_ancestor(node_id) for node_id in remaining
        ):
            return True
        # POSTCONDITION: WHEN any node remains non-terminal and eligible, return False.
        return False

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        # PRECONDITION: node_id must be registered in the scheduled DAG (raises NodeNotFoundError).
        if node_id not in self._dag.all_nodes():
            raise dag_engine_lite.NodeNotFoundError(
                f"Node '{node_id}' is not registered in the scheduled DAG",
                node_id,
            )
        self._sync_states()
        return self._states.get(node_id, dag_engine_lite.NodeState.PENDING)

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        self._sync_states()
        registered = self._dag.all_nodes()
        # POSTCONDITION: only currently registered nodes are reflected.
        return {
            node_id: self._states[node_id]
            for node_id in self._states
            if node_id in registered
        }

    def _sync_states(self) -> None:
        # Synchronize scheduling state with currently registered DAG nodes (also purges
        # identifiers of nodes removed from the graph).
        registered = self._dag.all_nodes()
        for stale in [node_id for node_id in self._states if node_id not in registered]:
            del self._states[stale]
        for node_id in sorted(registered):
            if node_id in self._states:
                continue
            if self._dependencies_satisfied(node_id):
                self._states[node_id] = dag_engine_lite.NodeState.READY
            else:
                self._states[node_id] = dag_engine_lite.NodeState.PENDING

    def _dependencies_satisfied(self, node_id: str) -> bool:
        for dependency in self._dag.get_dependencies(node_id):
            if self._states.get(dependency) is not dag_engine_lite.NodeState.SUCCEEDED:
                return False
        return True

    def _transitive_dependents(self, node_id: str) -> Set[str]:
        dependents: Set[str] = set()
        pending = [node_id]
        while pending:
            current = pending.pop()
            for dependent in self._dag.get_dependents(current):
                if dependent != node_id and dependent not in dependents:
                    dependents.add(dependent)
                    pending.append(dependent)
        return dependents

    def _has_blocking_ancestor(self, node_id: str) -> bool:
        seen: Set[str] = set()
        pending = [node_id]
        while pending:
            current = pending.pop()
            for dependency in self._dag.get_dependencies(current):
                if dependency in seen:
                    continue
                seen.add(dependency)
                state = self._states.get(dependency)
                if state is None:  # pragma: no cover (assumption: dependencies_validated_before_scheduling - every dependency is a synced node)
                    continue
                if state in _BLOCKING_STATES:
                    return True
                pending.append(dependency)
        return False


@singleton_type('system')
class DAGRunner(dag_engine_lite.DAGRunner):
    tier = system

    def __init__(self) -> None:
        # Collaborators resolved on demand from the ambient lifecycle registry.
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: dag_engine_lite.WaveScheduler = get_singleton(
            dag_engine_lite.WaveScheduler
        )
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def run(self, failure_policy: dag_engine_lite.FailurePolicy) -> dag_engine_lite.DAGRunReport:
        # PRECONDITION/POSTCONDITION: validate graph invariants before wave execution,
        # propagating NodeNotFoundError and CycleError to the caller.
        self._dag.validate()
        start_time = time.monotonic()
        self._results = {}
        halted = False
        while not halted and not self._scheduler.is_finished():
            # POSTCONDITION: execute ready waves sequentially; halt when none remain.
            wave = self._scheduler.next_wave()
            if not wave:  # pragma: no cover (assumption: validated_graph_no_stalled_waves - validated waves always progress)
                break
            for node_id in wave:
                definition = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)
                node_start = time.monotonic()
                value: Any = None
                error: Optional[Exception] = None
                retries_attempted = 0
                while True:
                    try:
                        value = definition.action()
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception (reified into NodeResult)
                        # POSTCONDITION: retry up to the configured retry count.
                        if retries_attempted < definition.retries:
                            retries_attempted += 1
                            continue
                        error = exc
                        break
                duration = time.monotonic() - node_start
                if error is None:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=value,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        error=error,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    # POSTCONDITION: apply the requested failure policy to the scheduler.
                    self._scheduler.mark_failed(node_id, failure_policy)
                    # POSTCONDITION: halt further wave execution under FAIL_FAST.
                    if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halted = True
                        break
        # POSTCONDITION: record default outcomes for unexecuted terminal nodes.
        for node_id, state in self._scheduler.get_all_states().items():
            if node_id not in self._results:
                self._results[node_id] = dag_engine_lite.NodeResult(
                    node_id=node_id,
                    state=state,
                )
        wall_clock_seconds = time.monotonic() - start_time
        critical_path, _ = self._dag.compute_critical_path(None)
        # POSTCONDITION: return a consolidated report of all node states and metrics.
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(self._dag.all_nodes()),
            succeeded_nodes=self._node_ids_in_state(dag_engine_lite.NodeState.SUCCEEDED),
            failed_nodes=self._node_ids_in_state(dag_engine_lite.NodeState.FAILED),
            skipped_nodes=self._node_ids_in_state(dag_engine_lite.NodeState.SKIPPED),
            cancelled_nodes=self._node_ids_in_state(dag_engine_lite.NodeState.CANCELLED),
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(critical_path),
            results=dict(self._results),
        )

    def _node_ids_in_state(self, state: dag_engine_lite.NodeState) -> Tuple[str, ...]:
        return tuple(
            sorted(
                node_id
                for node_id, result in self._results.items()
                if result.state is state
            )
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
# LAST_CLEANED: 2026-11-09T18:33:19Z
# LAST_CHANGED: 2026-11-09T18:17:41Z
# CHANGE: Pruned the dead cyclic-graph fallback path instead of annotating it. (1) topological_sort (formerly lines 167-168, topology='cycle_tuple_fallback'): a Kahn ordering shortfall necessarily implies a directed cycle, so the 'if cycle is None: cycle = tuple(sorted(n for n in self._nodes if indegree.get(n, 0) > 0))' fallback was unreachable dead logic and is now removed; topological_sort raises CycleError directly from the cycle sequence resolved by _find_cycle(). (2) Restructured _find_cycle to return Tuple[str, ...] using an empty tuple as the acyclic sentinel rather than Optional[None], so validate() now performs a single 'if cycle:' check whose acyclic and cyclic outcomes are both reachable and no dead narrowing branch remains (empty tuple is falsy; a detected cycle is always non-empty since it repeats the closing node). (3) Audited sibling branches for the same unreachable-fallback pattern and pruned the equivalent dead fallback in compute_critical_path ('leaf_nodes if leaf_nodes else order'): a non-empty acyclic graph always has at least one leaf, so the fallback to the full ordering could never execute; terminal-node selection now operates directly over the leaf candidate list. All reachable behavior is unchanged (cycle detection, CycleError message/sequence, topological ordering, critical path selection); no new pragma/pretense annotation was used because the dead logic was genuinely eliminated; static checks pass.
# COVERAGE_AUDIT: 2026-11-09T18:21:26Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-09T18:33:19Z
# PRETENSE_QA_AUDIT: 2026-11-09T18:32:56Z
# QA_AUDIT: 2026-11-09T18:21:13Z
# --- END AUTOFAB METADATA ---
