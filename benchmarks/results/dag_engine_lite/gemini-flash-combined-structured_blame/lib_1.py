# ==============================================================================
# Autofab Empirical Benchmark Flight Metrics
# Flight ID: flight_20261108_212439_gemini-flash_dag_engine_lite_combined
# Timestamp: 2026-11-08T21:24:39.862354+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-flash (Tier 2)
# Methodology: combined
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 4,979,867
#   Cached Inbound Tokens:   107,375,195
#   Outbound Tokens:         706,554
#   Total Tokens:            113,061,616
#   Financial Cost ($USD):   $3.4650
#   Wall Clock Duration:     5264.12s
#   Step Latencies (s):      []
#   Role Execution Rounds:   coverage: 7, lib: 9, pretense: 10, pretense_coverage: 4, pretense_qa: 23, qa: 8, test: 2 (Total: 63)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       43
#   Unit Tests Failed:       0
#   Line Coverage:           100.0%
#   Branch Coverage:         100.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface module for the synchronous DAG execution and wave scheduling engine."""

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

    def __str__(self) -> str:
        return self.message


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
        """Adds a task node to the graph.

        Args:
            node_id: Unique string identifier for the node.
            action: Zero-argument callable representing node computation.
            dependencies: Optional collection of upstream node identifiers.
            priority: Scheduling priority (higher executes earlier).
            retries: Number of permitted retry attempts upon exception.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Args:
            upstream_id: Identifier of the prerequisite node.
            downstream_id: Identifier of the dependent node.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.
        """
        ...

    @operation
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph.

        Args:
            node_id: Identifier to check.

        Returns:
            True if the node exists, False otherwise.
        """
        ...

    @operation
    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        Args:
            node_id: Identifier of the node to retrieve.

        Returns:
            The registered NodeDefinition.
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of upstream node identifiers.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of downstream node identifiers.
        """
        ...

    @operation
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph.

        Returns:
            Set of all registered node identifiers.
        """
        ...

    @operation
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        Tie-breaking between independent nodes is resolved first by priority (descending),
        then alphabetically by node_id (ascending).

        Returns:
            List of node identifiers in topological order.
        """
        ...

    @operation
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero (no dependencies).

        Returns:
            Set of root node identifiers.
        """
        ...

    @operation
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero (no dependents).

        Returns:
            Set of leaf node identifiers.
        """
        ...

    @operation
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]],
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph.

        Args:
            estimated_durations: Optional mapping of node identifiers to duration weights.
                Defaults to 1.0 per node if omitted.

        Returns:
            Tuple of (critical path node identifiers, total path weight).
        """
        ...


@singleton_type("system")
class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into sequential execution waves."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        Returns:
            List of node identifiers ready for execution, ordered by priority descending.
        """
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        Args:
            node_id: Identifier of the executing node.
        """
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        Args:
            node_id: Identifier of the completed node.
        """
        ...

    @operation
    def mark_failed(
        self,
        node_id: str,
        failure_policy: FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        Args:
            node_id: Identifier of the failed node.
            failure_policy: Failure policy applied upon failure.
        """
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        Returns:
            True if all nodes in the DAG have reached terminal states.
        """
        ...

    @operation
    def get_state(self, node_id: str) -> NodeState:
        """Retrieves the current execution state of a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Current NodeState.
        """
        ...

    @operation
    def get_all_states(self) -> Mapping[str, NodeState]:
        """Returns the execution state of every node in the graph.

        Returns:
            Mapping of node identifier to current NodeState, reflecting only currently registered nodes.
        """
        ...


@singleton_type("system")
class DAGRunner(Singleton[SystemTier], Protocol):
    """Executes a DAG sequentially to completion under failure policies."""

    @operation
    def run(
        self,
        failure_policy: FailurePolicy,
    ) -> DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure.

        Args:
            failure_policy: Failure policy applied upon node action failure.

        Returns:
            Consolidated DAGRunReport recording all node outcomes and metrics.
        """
        ...

# --- AUTOFAB METADATA ---
# LAST_CLEANED: 2026-11-08T21:32:50Z
# LAST_CHANGED: 2026-11-08T21:32:50Z
# CHANGE: Initial implementation of DAG engine protocol stubs, dataclasses, and enums
# --- END AUTOFAB METADATA ---


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
    Singleton,
    SystemTier,
    get_default_registry,
    get_singleton,
)
from . import dag_engine_lite


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    """
    tier: str = "system"

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
        """Adds a task node to the graph.

        GROUNDING:
        - Verifies node_id is not already present in _nodes; raises dag_engine_lite.DuplicateNodeError if present.
        - Constructs immutable dag_engine_lite.NodeDefinition with frozen dependency set without eagerly checking dependency existence.
        - Inserts definition into _nodes, registering empty neighbor sets in _upstream and _downstream if absent.
        - Adds directed edges from each dependency to node_id, deferring existence validation.
        """
        if node_id in self._nodes:
            raise dag_engine_lite.DuplicateNodeError(
                message=f"Node '{node_id}' already registered in DAG",
                node_id=node_id,
            )

        deps: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
        definition = dag_engine_lite.NodeDefinition(
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
        """Adds a directed dependency edge where downstream depends on upstream.

        GROUNDING:
        - Verifies presence of upstream_id and downstream_id in _nodes.
        - Raises dag_engine_lite.NodeNotFoundError if either identifier is missing.
        - Updates _upstream and _downstream sets.
        """
        if upstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Upstream node '{upstream_id}' not found",
                node_id=upstream_id,
            )
        if downstream_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Downstream node '{downstream_id}' not found",
                node_id=downstream_id,
            )

        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

        old_def = self._nodes[downstream_id]
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
        """Removes a node and all incident dependency edges from the graph.

        GROUNDING:
        - Verifies presence of node_id in _nodes.
        - Raises dag_engine_lite.NodeNotFoundError if absent.
        - Removes node_id from all incident upstream and downstream neighbor sets.
        - Deletes node_id from _nodes, _upstream, and _downstream.
        """
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' does not exist in graph",
                node_id=node_id,
            )

        # Remove from downstream nodes that depended on node_id
        for downstream in self._downstream.get(node_id, set()):
            if downstream in self._upstream:
                self._upstream[downstream].discard(node_id)
            if downstream in self._nodes:
                d_def = self._nodes[downstream]
                self._nodes[downstream] = dag_engine_lite.NodeDefinition(
                    node_id=d_def.node_id,
                    action=d_def.action,
                    dependencies=frozenset(self._upstream[downstream]),
                    priority=d_def.priority,
                    retries=d_def.retries,
                )

        # Remove from upstream nodes that node_id depended on
        for upstream in self._upstream.get(node_id, set()):
            if upstream in self._downstream:
                self._downstream[upstream].discard(node_id)

        del self._nodes[node_id]
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

        scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        getattr(scheduler, "_states").pop(node_id, None)

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph.

        GROUNDING:
        - Checks membership of node_id in _nodes.
        """
        return node_id in self._nodes

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        GROUNDING:
        - Looks up node_id in _nodes.
        - Raises dag_engine_lite.NodeNotFoundError if node_id is not present.
        """
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' does not exist in graph",
                node_id=node_id,
            )
        return self._nodes[node_id]

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        GROUNDING:
        - Verifies node_id in _nodes, raising dag_engine_lite.NodeNotFoundError if missing.
        - Returns a copy of _upstream[node_id].
        """
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' does not exist in graph",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        GROUNDING:
        - Verifies node_id in _nodes, raising dag_engine_lite.NodeNotFoundError if missing.
        - Returns a copy of _downstream[node_id].
        """
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' does not exist in graph",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph.

        GROUNDING:
        - Returns a copy of set(_nodes.keys()).
        """
        return set(self._nodes.keys())

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity.

        GROUNDING:
        - Verifies that every dependency in every node definition exists in _nodes, raising dag_engine_lite.NodeNotFoundError if missing.
        - Executes depth-first search cycle detection with active recursion path tracking.
        - Raises dag_engine_lite.CycleError containing the cycle sequence upon detecting any directed cycle.
        """
        for node_id in sorted(self._nodes.keys()):
            for dep in sorted(self._nodes[node_id].dependencies):
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dep}' referenced by node '{node_id}' does not exist",
                        node_id=dep,
                    )

        state: Dict[str, int] = {}
        path: List[str] = []

        def dfs(u: str) -> None:
            state[u] = 1
            path.append(u)
            for v in sorted(self._downstream.get(u, set())):
                if state.get(v, 0) == 1:
                    idx = path.index(v)
                    cycle_nodes = tuple(path[idx:] + [v])
                    raise dag_engine_lite.CycleError(
                        message=f"Dependency cycle detected: {' -> '.join(cycle_nodes)}",
                        cycle=cycle_nodes,
                    )
                if state.get(v, 0) == 0:
                    dfs(v)
            path.pop()
            state[u] = 2

        for node in sorted(self._nodes.keys()):
            if state.get(node, 0) == 0:
                dfs(node)

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        GROUNDING:
        - Computes in-degree counts from _upstream mapping.
        - Initializes ready list with nodes having in-degree zero, sorted by priority descending then node_id ascending.
        - Iteratively extracts candidate with highest priority, appends to order, and decrements downstream in-degrees.
        - Inserts newly zero in-degree nodes maintaining priority descending then node_id ascending order.
        - Raises dag_engine_lite.CycleError containing the cycle sequence if ordered count does not equal len(_nodes).
        - Returns computed topological order list.
        """
        for node_id in sorted(self._nodes.keys()):
            for dep in sorted(self._nodes[node_id].dependencies):
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dep}' referenced by node '{node_id}' does not exist",
                        node_id=dep,
                    )

        in_degree: Dict[str, int] = {
            nid: len([p for p in self._upstream.get(nid, set()) if p in self._nodes])
            for nid in self._nodes
        }

        ready: List[str] = [nid for nid, deg in in_degree.items() if deg == 0]
        ready.sort(key=lambda nid: (-self._nodes[nid].priority, nid))

        order: List[str] = []
        while ready:
            cand = ready.pop(0)
            order.append(cand)
            newly_ready: List[str] = []
            for downstream in sorted(self._downstream.get(cand, set())):
                if downstream in in_degree:
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0:
                        newly_ready.append(downstream)
            for nr in newly_ready:
                ready.append(nr)
            ready.sort(key=lambda nid: (-self._nodes[nid].priority, nid))

        if len(order) != len(self._nodes):
            self.validate()
            # If validate didn't catch (should be unreachable), raise fallback CycleError
            raise dag_engine_lite.CycleError(  # unreachable (assumption: self.validate raises CycleError on cyclic graph)
                message="Cycle detected in DAG",
                cycle=(),
            )

        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero.

        GROUNDING:
        - Iterates over _nodes, collecting node identifiers whose _upstream set is empty.
        - Returns set of root node identifiers.
        """
        return {
            nid for nid in self._nodes
            if not any(p in self._nodes for p in self._upstream.get(nid, set()))
        }

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero.

        GROUNDING:
        - Iterates over _nodes, collecting node identifiers whose _downstream set is empty.
        - Returns set of leaf node identifiers.
        """
        return {
            nid for nid in self._nodes
            if not any(d in self._nodes for d in self._downstream.get(nid, set()))
        }

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph.

        GROUNDING:
        - Computes topological order using topological_sort().
        - Resolves duration weights mapping defaulting to 1.0 for unspecified nodes.
        - Computes earliest completion times using dynamic programming: earliest[node] = max((earliest[p] for p in upstream), default=0.0) + duration[node].
        - Identifies terminal node with maximum completion time.
        - Backtracks through upstream dependencies selecting predecessor yielding maximum earliest time.
        - Returns reversed path list and total path duration weight.
        """
        if not self._nodes:
            return [], 0.0

        order = self.topological_sort()
        durations: Dict[str, float] = {}
        for nid in self._nodes:
            durations[nid] = (
                float(estimated_durations[nid])
                if estimated_durations is not None and nid in estimated_durations
                else 1.0
            )

        earliest: Dict[str, float] = {}
        best_predecessor: Dict[str, Optional[str]] = {}

        for node in order:
            upstream = [p for p in self._upstream.get(node, set()) if p in self._nodes]
            if not upstream:
                earliest[node] = durations[node]
                best_predecessor[node] = None
            else:
                best_p = max(sorted(upstream), key=lambda p: earliest[p])
                earliest[node] = earliest[best_p] + durations[node]
                best_predecessor[node] = best_p

        terminal_node = max(sorted(order), key=lambda n: earliest[n])
        path: List[str] = []
        curr: Optional[str] = terminal_node
        while curr is not None:
            path.append(curr)
            curr = best_predecessor.get(curr)
        path.reverse()
        total_weight = earliest[terminal_node]
        return path, total_weight


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states dictionary mapping node identifiers to dag_engine_lite.NodeState.
    - Synchronizes dynamic node state by discovering registered nodes from _dag.all_nodes(), initializing root nodes to dag_engine_lite.NodeState.READY and non-root nodes to dag_engine_lite.NodeState.PENDING.
    """
    tier: str = "system"

    def __init__(self, dag: Optional[dag_engine_lite.DAG] = None) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = dag
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _get_dag(self) -> dag_engine_lite.DAG:
        if self._dag is None:
            self._dag = get_singleton(dag_engine_lite.DAG)
        return self._dag

    def _sync_states(self) -> None:
        dag = self._get_dag()
        all_active = dag.all_nodes()
        roots = dag.find_roots()
        for nid in all_active:
            if nid not in self._states:
                if nid in roots:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        GROUNDING:
        - Ensures _states contains all nodes from _dag, initializing roots to dag_engine_lite.NodeState.READY and non-roots to dag_engine_lite.NodeState.PENDING.
        - Gathers all nodes currently in dag_engine_lite.NodeState.READY whose upstream dependencies are all dag_engine_lite.NodeState.SUCCEEDED.
        - Sorts candidate nodes by definition priority descending, then node_id ascending.
        - Returns ordered list of ready node identifiers.
        """
        self._sync_states()
        dag = self._get_dag()
        candidates: List[str] = []
        for nid, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                upstream = dag.get_dependencies(nid)
                if all(self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstream):
                    candidates.append(nid)
        candidates.sort(key=lambda nid: (-dag.get_node(nid).priority, nid))
        return candidates

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        GROUNDING:
        - Sets _states[node_id] to dag_engine_lite.NodeState.RUNNING.
        """
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        GROUNDING:
        - Sets _states[node_id] to dag_engine_lite.NodeState.SUCCEEDED.
        - Inspects downstream dependents of node_id.
        - Promotes any dependent currently in dag_engine_lite.NodeState.PENDING to dag_engine_lite.NodeState.READY if all its upstream dependencies are dag_engine_lite.NodeState.SUCCEEDED.
        """
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        dag = self._get_dag()
        for dep_id in dag.get_dependents(node_id):
            if self._states.get(dep_id) == dag_engine_lite.NodeState.PENDING:
                upstream = dag.get_dependencies(dep_id)
                if all(self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstream):
                    self._states[dep_id] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        GROUNDING:
        - Sets _states[node_id] to dag_engine_lite.NodeState.FAILED.
        - Transitions all non-terminal nodes to dag_engine_lite.NodeState.CANCELLED if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST.
        - Traverses transitive downstream dependents and marks non-terminal dependents as dag_engine_lite.NodeState.SKIPPED if failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM.
        - Retains non-terminal states for unblocked independent nodes if failure_policy is dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR, transitioning blocked dependents of failed nodes to dag_engine_lite.NodeState.SKIPPED.
        """
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        dag = self._get_dag()

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid in list(self._states.keys()):
                if nid != node_id and self._states[nid] in (
                    dag_engine_lite.NodeState.PENDING,
                    dag_engine_lite.NodeState.READY,
                    dag_engine_lite.NodeState.RUNNING,
                ):
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            queue = list(dag.get_dependents(node_id))
            visited = set(queue)
            while queue:
                curr = queue.pop(0)
                if self._states.get(curr) in (
                    dag_engine_lite.NodeState.PENDING,
                    dag_engine_lite.NodeState.READY,
                ):
                    self._states[curr] = dag_engine_lite.NodeState.SKIPPED
                for nxt in dag.get_dependents(curr):
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        GROUNDING:
        - Synchronizes _states with all nodes currently registered in _dag.all_nodes().
        - Checks whether every node in the DAG is present in _states and in a terminal state (SUCCEEDED, FAILED, SKIPPED, CANCELLED).
        - Returns True if all registered DAG nodes have reached terminal states or if no ready nodes remain and unexecuted nodes are blocked by failed dependencies, or if DAG is empty; False otherwise.
        """
        self._sync_states()
        dag = self._get_dag()
        all_nodes = dag.all_nodes()
        if not all_nodes:
            return True

        if any(self._states.get(nid) == dag_engine_lite.NodeState.RUNNING for nid in all_nodes):
            return False

        return len(self.next_wave()) == 0

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node.

        GROUNDING:
        - Checks whether node_id is registered in _dag.all_nodes(); raises dag_engine_lite.NodeNotFoundError if absent.
        - Ensures _states contains node_id by synchronizing with _dag.all_nodes() if absent.
        - Returns _states[node_id].
        """
        dag = self._get_dag()
        if not dag.has_node(node_id):
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' does not exist in graph",
                node_id=node_id,
            )
        self._sync_states()
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph.

        GROUNDING:
        - Ensures _states contains all nodes from _dag.all_nodes().
        - Returns a shallow copy of _states mapping filtered to only include nodes currently present in _dag.all_nodes().
        """
        self._sync_states()
        dag = self._get_dag()
        all_nodes = dag.all_nodes()
        return {nid: self._states[nid] for nid in all_nodes if nid in self._states}


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine_lite.DAG) and WaveScheduler service via get_singleton(dag_engine_lite.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, and _results mapping.
    """
    tier: str = "system"

    def __init__(
        self,
        dag: Optional[dag_engine_lite.DAG] = None,
        scheduler: Optional[dag_engine_lite.WaveScheduler] = None,
    ) -> None:
        self._dag: Optional[dag_engine_lite.DAG] = dag
        self._scheduler: Optional[dag_engine_lite.WaveScheduler] = scheduler
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def _get_dag(self) -> dag_engine_lite.DAG:
        if self._dag is None:
            self._dag = get_singleton(dag_engine_lite.DAG)
        return self._dag

    def _get_scheduler(self) -> dag_engine_lite.WaveScheduler:
        if self._scheduler is None:
            self._scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        return self._scheduler

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure.

        GROUNDING:
        - Validates _dag using _dag.validate(), allowing cycle or missing dependency exceptions to raise immediately.
        - Initializes start wall-clock time and empty _results mapping.
        - Loops while _scheduler.is_finished() returns False and retrieves the next wave from _scheduler.next_wave().
        - Halts wave loop when next wave is empty.
        - Dispatches each ready wave node sequentially, marking it RUNNING in _scheduler.
        - Executes node action with retry attempts up to definition.retries upon exception.
        - Records dag_engine_lite.NodeResult(SUCCEEDED) and marks SUCCEEDED in _scheduler on success.
        - Records dag_engine_lite.NodeResult(FAILED) and marks FAILED in _scheduler with failure_policy on failure after retries.
        - Halts further wave execution when failure_policy is FAIL_FAST and a node has failed.
        - Populates _results with default unexecuted dag_engine_lite.NodeResult records for terminal skipped or cancelled nodes from _scheduler states.
        - Computes critical path using _dag.compute_critical_path().
        - Gathers succeeded, failed, skipped, and cancelled node tuples from _results and _scheduler states.
        - Returns consolidated dag_engine_lite.DAGRunReport.
        """
        dag = self._get_dag()
        scheduler = self._get_scheduler()

        dag.validate()

        start_time = time.monotonic()
        self._results.clear()

        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            if not wave:  # unreachable (assumption: empty wave loop stall breaker per grounding)
                break
            stop_execution = False
            for node_id in wave:
                scheduler.mark_running(node_id)
                node_def = dag.get_node(node_id)

                retries_attempted = 0
                node_start = time.monotonic()
                node_val = None
                last_error: Optional[Exception] = None
                succeeded = False

                max_retries = max(0, node_def.retries)
                for attempt in range(max_retries + 1):
                    if attempt > 0:
                        retries_attempted += 1
                    try:
                        node_val = node_def.action()
                        succeeded = True
                        last_error = None
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        last_error = exc

                node_duration = time.monotonic() - node_start

                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=node_val,
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
                        stop_execution = True
                        break

            if stop_execution:
                break

        all_states = scheduler.get_all_states()
        for nid, state in all_states.items():
            if nid not in self._results:
                self._results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=state,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        wall_clock_seconds = time.monotonic() - start_time
        critical_path_nodes, _ = dag.compute_critical_path(None)

        succeeded_nodes = tuple(
            nid for nid, res in self._results.items()
            if res.state == dag_engine_lite.NodeState.SUCCEEDED
        )
        failed_nodes = tuple(
            nid for nid, res in self._results.items()
            if res.state == dag_engine_lite.NodeState.FAILED
        )
        skipped_nodes = tuple(
            nid for nid, res in self._results.items()
            if res.state == dag_engine_lite.NodeState.SKIPPED
        )
        cancelled_nodes = tuple(
            nid for nid, res in self._results.items()
            if res.state == dag_engine_lite.NodeState.CANCELLED
        )

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock_seconds,
            critical_path=tuple(critical_path_nodes),
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
# LAST_CLEANED: 2026-11-08T22:52:23Z
# LAST_CHANGED: 2026-11-08T22:51:22Z
# CHANGE: Annotate unreachable fallback CycleError in topological_sort with pragma no cover
# COVERAGE_AUDIT: 2026-11-08T22:52:20Z
# PRETENSE_COVERAGE_AUDIT: 2026-11-08T22:52:23Z
# PRETENSE_QA_AUDIT: 2026-11-08T22:51:56Z
# QA_AUDIT: 2026-11-08T22:51:52Z
# --- END AUTOFAB METADATA ---
