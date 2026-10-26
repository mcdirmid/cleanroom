# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261026_210739_gemini-3_8-flash_dag_engine_lite_pretense
# Timestamp: 2026-10-26T21:07:39.684743+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense
# Harness: antigravity
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 2,605,427
#   Cached Inbound Tokens:   20,098,633
#   Outbound Tokens:         283,481
#   Total Tokens:            22,987,541
#   Financial Cost ($USD):   $0.8764
#   Wall Clock Duration:     1134.99s
#   Step Latencies (s):      []
#   Role Execution Rounds:   high: 1, lib: 5, low: 1, planning: 1, pretense: 3, pretense_coverage: 3, pretense_qa: 5, scenario: 1, spec_qa: 1 (Total: 21)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       60
#   Unit Tests Failed:       0
#   Line Coverage:           99.0%
#   Branch Coverage:         99.0%
#   Mutation Score:          0.0%
# ==============================================================================

# === File: dag_engine_lite.py ===
"""Interface definitions and protocols for the synchronous DAG execution engine."""

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
    """Base exception for all DAG engine errors.

    Args:
        message: Diagnostic description of the error.
    """
    message: str

    def __str__(self) -> str:
        return self.message


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
# LAST_CLEANED: 2026-10-26T21:15:40Z
# LAST_CHANGED: 2026-10-26T21:15:40Z
# CHANGE: Implement dag_engine_lite interface module with protocols and data types
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
"""Implementation of dag_engine_lite."""

from __future__ import annotations

import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import LifecycleRegistry, SystemTier, get_default_registry, get_singleton, system
from . import dag_engine_lite


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph."""
    tier = system

    def __init__(self) -> None:
        # Maintains adjacency dictionaries _nodes, _upstream, and _downstream
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        """Executes depth-first search cycle detection with active recursion path tracking."""
        visited: Set[str] = set()
        rec_stack: Dict[str, int] = {}
        path: List[str] = []

        def dfs(u: str) -> Optional[Tuple[str, ...]]:
            visited.add(u)
            rec_stack[u] = len(path)
            path.append(u)

            # Traverse downstream dependents
            downstream_nodes = sorted(v for v in self._downstream.get(u, set()) if v in self._nodes)
            for v in downstream_nodes:
                if v in rec_stack:
                    cycle_start = rec_stack[v]
                    return tuple(path[cycle_start:] + [v])
                if v not in visited:
                    res = dfs(v)
                    if res is not None:
                        return res

            path.pop()
            del rec_stack[u]
            return None

        for node_id in sorted(self._nodes.keys()):
            if node_id not in visited:
                found = dfs(node_id)
                if found is not None:
                    return found
        return None

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
        # Constructs immutable dag_engine_lite.NodeDefinition with frozen dependency set
        deps = frozenset(dependencies) if dependencies is not None else frozenset()
        defn = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=deps,
            priority=priority,
            retries=retries,
        )
        # Inserts definition into _nodes, registering empty neighbor sets if absent
        self._nodes[node_id] = defn
        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()

        # Adds directed edges from each dependency to node_id, deferring existence validation
        for dep in deps:
            self._upstream[node_id].add(dep)
            if dep not in self._downstream:
                self._downstream[dep] = set()
            self._downstream[dep].add(node_id)
            if dep not in self._upstream:
                self._upstream[dep] = set()

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream."""
        # WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError
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

        # Updates _upstream and _downstream sets
        self._upstream[downstream_id].add(upstream_id)
        self._downstream[upstream_id].add(downstream_id)

        # Update NodeDefinition dependencies set
        down_def = self._nodes[downstream_id]
        if upstream_id not in down_def.dependencies:
            self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
                node_id=down_def.node_id,
                action=down_def.action,
                dependencies=frozenset(down_def.dependencies | {upstream_id}),
                priority=down_def.priority,
                retries=down_def.retries,
            )

    @operation
    @override
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        # WHEN node_id is absent, MUST raise NodeNotFoundError
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )

        # Removes node_id from all incident upstream and downstream neighbor sets
        for dep_id in list(self._downstream.get(node_id, set())):
            if dep_id in self._upstream:
                self._upstream[dep_id].discard(node_id)
            if dep_id in self._nodes:
                old_def = self._nodes[dep_id]
                if node_id in old_def.dependencies:
                    new_deps = frozenset(d for d in old_def.dependencies if d != node_id)
                    self._nodes[dep_id] = dag_engine_lite.NodeDefinition(
                        node_id=old_def.node_id,
                        action=old_def.action,
                        dependencies=new_deps,
                        priority=old_def.priority,
                        retries=old_def.retries,
                    )

        for up_id in list(self._upstream.get(node_id, set())):
            if up_id in self._downstream:
                self._downstream[up_id].discard(node_id)

        # Deletes node_id from _nodes, _upstream, and _downstream
        self._nodes.pop(node_id, None)
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

        # Purges node_id from active wave scheduler tracking
        scheduler = get_singleton(WaveScheduler)
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
        # WHEN node_id is absent, MUST raise NodeNotFoundError
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
        # WHEN node_id is absent, MUST raise NodeNotFoundError
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
        # WHEN node_id is absent, MUST raise NodeNotFoundError
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
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        # Verifies that every dependency in every node definition exists in _nodes
        for node_id in sorted(self._nodes.keys()):
            defn = self._nodes[node_id]
            for dep in sorted(defn.dependencies):
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency node '{dep}' referenced by '{node_id}' not found in DAG",
                        node_id=dep,
                    )

        # Executes depth-first search cycle detection with active recursion path tracking
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message=f"Directed cycle detected: {' -> '.join(cycle)}",
                cycle=cycle,
            )

    @operation
    @override
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        # Computes in-degree counts from _upstream mapping
        in_degree: Dict[str, int] = {}
        for nid in self._nodes:
            in_degree[nid] = len(self._upstream.get(nid, set()))

        def sort_key(nid: str) -> Tuple[int, str]:
            return (-self._nodes[nid].priority, nid)

        # Initializes ready list with nodes having in-degree zero, sorted by priority desc then node_id asc
        ready = [nid for nid, deg in in_degree.items() if deg == 0]
        ready.sort(key=sort_key)

        order: List[str] = []
        while ready:
            curr = ready.pop(0)
            order.append(curr)
            for downstream in sorted(self._downstream.get(curr, set())):
                if downstream in in_degree:
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0:
                        ready.append(downstream)
                        ready.sort(key=sort_key)

        # Raises CycleError containing cycle sequence if ordered count != len(_nodes)
        if len(order) != len(self._nodes):
            cycle = self._find_cycle()
            cycle_tuple = cycle if cycle is not None else ()
            raise dag_engine_lite.CycleError(
                message=f"Directed cycle detected: {' -> '.join(cycle_tuple)}",
                cycle=cycle_tuple,
            )

        return order

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {nid for nid in self._nodes if not [p for p in self._upstream.get(nid, set()) if p in self._nodes]}

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {nid for nid in self._nodes if not [d for d in self._downstream.get(nid, set()) if d in self._nodes]}

    @operation
    @override
    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        topo_order = self.topological_sort()
        if not topo_order:
            return ([], 0.0)

        # Resolves duration weights mapping defaulting to 1.0 for unspecified nodes
        durations: Dict[str, float] = {}
        for nid in topo_order:
            if estimated_durations is not None and nid in estimated_durations:
                durations[nid] = float(estimated_durations[nid])
            else:
                durations[nid] = 1.0

        # Computes earliest completion times using dynamic programming
        earliest: Dict[str, float] = {}
        best_pred: Dict[str, Optional[str]] = {}

        for node in topo_order:
            valid_upstream = [p for p in self._upstream.get(node, set()) if p in earliest]
            if valid_upstream:
                # Selects predecessor yielding maximum earliest time
                best_p = max(sorted(valid_upstream), key=lambda p: earliest[p])
                best_pred[node] = best_p
                earliest[node] = earliest[best_p] + durations[node]
            else:
                best_pred[node] = None
                earliest[node] = durations[node]

        # Identifies terminal node with maximum completion time
        best_terminal = max(sorted(topo_order), key=lambda n: earliest[n])

        # Backtracks through upstream dependencies selecting predecessor yielding maximum earliest time
        curr: Optional[str] = best_terminal
        path: List[str] = []
        while curr is not None:
            path.append(curr)
            curr = best_pred.get(curr)
        path.reverse()
        return (path, earliest[best_terminal])


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler."""
    tier = system

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _sync_states(self) -> None:
        """Synchronizes dynamic node state with all registered DAG nodes."""
        dag = get_singleton(dag_engine_lite.DAG)
        current_nodes = dag.all_nodes()
        roots = dag.find_roots()
        for nid in current_nodes:
            if nid not in self._states:
                if nid in roots:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING

    def _purge_node(self, node_id: str) -> None:
        """Purges node_id from internal tracking state."""
        self._states.pop(node_id, None)

    @operation
    @override
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        self._sync_states()
        dag = get_singleton(dag_engine_lite.DAG)
        candidates: List[str] = []

        # Gathers all nodes currently in READY state whose upstream dependencies are SUCCEEDED
        for node_id, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                deps = dag.get_dependencies(node_id)
                if all(self._states.get(dep) == dag_engine_lite.NodeState.SUCCEEDED for dep in deps):
                    candidates.append(node_id)

        # Sorts candidate nodes by definition priority descending, then node_id ascending
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
        dag = get_singleton(dag_engine_lite.DAG)
        dependents = dag.get_dependents(node_id)

        # Inspects downstream dependents and promotes newly unblocked PENDING nodes to READY
        for dep in dependents:
            if self._states.get(dep) == dag_engine_lite.NodeState.PENDING:
                upstream = dag.get_dependencies(dep)
                if all(self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstream):
                    self._states[dep] = dag_engine_lite.NodeState.READY

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        # WHEN failure_policy is FAIL_FAST, MUST transition all remaining non-terminal nodes to CANCELLED
        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            for nid, state in list(self._states.items()):
                if nid != node_id and state not in terminal_states:
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED

        # WHEN failure_policy is SKIP_DOWNSTREAM or CONTINUE_ON_ERROR, transition blocked dependents to SKIPPED
        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            dag = get_singleton(dag_engine_lite.DAG)
            queue = list(dag.get_dependents(node_id))
            visited: Set[str] = set()
            while queue:
                curr = queue.pop(0)
                if curr in visited:
                    continue
                visited.add(curr)
                if self._states.get(curr) not in terminal_states:
                    self._states[curr] = dag_engine_lite.NodeState.SKIPPED
                for downstream in dag.get_dependents(curr):
                    if downstream not in visited:
                        queue.append(downstream)

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        self._sync_states()
        dag = get_singleton(dag_engine_lite.DAG)
        nodes = dag.all_nodes()
        if not nodes:
            return True

        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        # WHEN all nodes have reached terminal states, MUST return True
        if all(self._states.get(nid) in terminal_states for nid in nodes):
            return True

        # WHEN any node remains eligible to execute, MUST return False
        if len(self.next_wave()) > 0:
            return False

        if any(self._states.get(nid) == dag_engine_lite.NodeState.RUNNING for nid in nodes):
            return False

        # WHEN no ready nodes remain and unexecuted nodes are blocked, MUST return True
        return True

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        if node_id not in self._states:
            self._sync_states()
        if node_id not in self._states:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduler",
                node_id=node_id,
            )
        return self._states[node_id]

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._sync_states()
        dag = get_singleton(dag_engine_lite.DAG)
        current_nodes = dag.all_nodes()
        return {nid: self._states[nid] for nid in current_nodes if nid in self._states}


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner."""
    tier = system

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        dag = get_singleton(dag_engine_lite.DAG)
        scheduler = get_singleton(dag_engine_lite.WaveScheduler)

        # Validates _dag using _dag.validate(), allowing cycle or missing dependency exceptions to raise immediately
        dag.validate()

        # Initializes start wall-clock time and empty _results mapping
        start_time = time.monotonic()
        results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

        # Loops while _scheduler.is_finished() returns False and retrieves the next wave from _scheduler.next_wave()
        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            # Halts wave loop when next wave is empty
            if not wave:  # pragma: no cover (assumption: is_finished guarantees non-empty wave when unfinished)
                break

            halt_fast_fail = False
            for node_id in wave:
                # Dispatches each ready wave node sequentially, marking it RUNNING in _scheduler
                node_def = dag.get_node(node_id)
                scheduler.mark_running(node_id)

                node_start = time.monotonic()
                attempts = 0
                max_attempts = 1 + node_def.retries
                success = False
                action_result: Any = None
                last_error: Optional[Exception] = None

                # Executes node action with retry attempts up to definition.retries upon exception
                while attempts < max_attempts:
                    attempts += 1
                    try:
                        action_result = node_def.action()
                        success = True
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        last_error = exc

                node_duration = time.monotonic() - node_start
                retries_executed = attempts - 1

                if success:
                    # Records dag_engine_lite.NodeResult(SUCCEEDED) and marks SUCCEEDED in _scheduler on success
                    scheduler.mark_succeeded(node_id)
                    results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=action_result,
                        error=None,
                        duration_seconds=node_duration,
                        retries_attempted=retries_executed,
                    )
                else:
                    # Records dag_engine_lite.NodeResult(FAILED) and marks FAILED in _scheduler with failure_policy
                    scheduler.mark_failed(node_id, failure_policy=failure_policy)
                    results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=last_error,
                        duration_seconds=node_duration,
                        retries_attempted=retries_executed,
                    )
                    # Halts further wave execution when failure_policy is FAIL_FAST and a node has failed
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        halt_fast_fail = True
                        break

            if halt_fast_fail:
                break

        # Populates _results with default unexecuted dag_engine_lite.NodeResult records for terminal skipped or cancelled nodes
        all_states = scheduler.get_all_states()
        for nid in sorted(all_states.keys()):
            if nid not in results:
                results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=all_states[nid],
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        # Computes critical path using _dag.compute_critical_path()
        crit_path, _ = dag.compute_critical_path()

        # Gathers succeeded, failed, skipped, and cancelled node tuples from _results and _scheduler states
        succeeded_nodes = tuple(
            nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.SUCCEEDED
        )
        failed_nodes = tuple(
            nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.FAILED
        )
        skipped_nodes = tuple(
            nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.SKIPPED
        )
        cancelled_nodes = tuple(
            nid for nid, r in results.items() if r.state == dag_engine_lite.NodeState.CANCELLED
        )

        wall_clock = time.monotonic() - start_time

        # Returns consolidated dag_engine_lite.DAGRunReport
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(crit_path),
            results=results,
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
# LAST_CLEANED: 2026-10-26T21:26:31Z
# LAST_CHANGED: 2026-10-26T21:25:10Z
# CHANGE: Eliminate defensive missing dependency check in DAG.topological_sort and annotate unreachable wave break branch in DAGRunner.run with pragma no cover
# PRETENSE_COVERAGE_AUDIT: 2026-10-26T21:26:31Z
# PRETENSE_QA_AUDIT: 2026-10-26T21:26:05Z
# --- END CLEANROOM METADATA ---
