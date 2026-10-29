# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261028_231534_gemini-3_8-flash_dag_engine_lite_pretense
# Timestamp: 2026-10-28T23:15:34.859678+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense
# Harness: antigravity
# Run Index: 1
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 3,527,025
#   Cached Inbound Tokens:   41,821,304
#   Outbound Tokens:         384,553
#   Total Tokens:            45,732,882
#   Financial Cost ($USD):   $1.5521
#   Wall Clock Duration:     3105.55s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 3, pretense: 9, pretense_coverage: 2, pretense_qa: 9 (Total: 23)
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
from __future__ import annotations
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from dataclasses import dataclass
from support.lib.lifecycle import Singleton, SystemTier, system
import enum

# Requirements specified in dag_engine_lite.pyi

T = TypeVar('T')

@dataclass
class DAGError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class CycleError(DAGError):
    cycle: Tuple[str, ...]


@dataclass
class NodeNotFoundError(DAGError):
    node_id: str


@dataclass
class NodeExecutionError(DAGError):
    node_id: str
    cause: Exception


class NodeState(enum.Enum):
    PENDING = 'pending'
    READY = 'ready'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    SKIPPED = 'skipped'


class FailurePolicy(enum.Enum):
    FAIL_FAST = 'fail_fast'
    CONTINUE_ON_ERROR = 'continue_on_error'
    SKIP_DOWNSTREAM = 'skip_downstream'


@dataclass(frozen=True)
class NodeDefinition(Generic[T]):
    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    retries: int = 0


@dataclass(frozen=True)
class NodeResult(Generic[T]):
    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0


@dataclass(frozen=True)
class DAGRunReport:
    total_nodes: int
    succeeded_nodes: Tuple[str, ...]
    failed_nodes: Tuple[str, ...]
    skipped_nodes: Tuple[str, ...]
    cancelled_nodes: Tuple[str, ...]
    wall_clock_seconds: float
    critical_path: Tuple[str, ...]
    results: Mapping[str, NodeResult[Any]]


class DAG(Singleton[SystemTier], Protocol):
    def add_node(self, node_id: str, action: Callable[[], Any], dependencies: Optional[Collection[str]]=None, priority: int=0, retries: int=0) -> None:
        ...

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        ...

    def remove_node(self, node_id: str) -> None:
        ...

    def has_node(self, node_id: str) -> bool:
        ...

    def get_node(self, node_id: str) -> NodeDefinition[Any]:
        ...

    def get_dependencies(self, node_id: str) -> Set[str]:
        ...

    def get_dependents(self, node_id: str) -> Set[str]:
        ...

    def all_nodes(self) -> Set[str]:
        ...

    def validate(self) -> None:
        ...

    def topological_sort(self) -> List[str]:
        ...

    def find_roots(self) -> Set[str]:
        ...

    def find_leaves(self) -> Set[str]:
        ...

    def compute_critical_path(self, estimated_durations: Optional[Mapping[str, float]]=None) -> Tuple[List[str], float]:
        ...


class WaveScheduler(Singleton[SystemTier], Protocol):
    def next_wave(self) -> List[str]:
        ...

    def mark_running(self, node_id: str) -> None:
        ...

    def mark_succeeded(self, node_id: str) -> None:
        ...

    def mark_failed(self, node_id: str, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> None:
        ...

    def is_finished(self) -> bool:
        ...

    def get_state(self, node_id: str) -> NodeState:
        ...

    def get_all_states(self) -> Mapping[str, NodeState]:
        ...


class DAGRunner(Singleton[SystemTier], Protocol):
    def run(self, failure_policy: FailurePolicy=FailurePolicy.FAIL_FAST) -> DAGRunReport:
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-28T23:22:29Z
# LAST_CHANGED: 2026-10-28T23:22:29Z
# CHANGE: Initial implementation of DAG engine protocol definitions, data types, and unfrozen custom exception classes
# --- END CLEANROOM METADATA ---


# === File: dag_engine_lite_impl.py ===
from __future__ import annotations
import time
from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.lifecycle import LifecycleRegistry, Singleton, get_default_registry, get_singleton, system
from . import dag_engine_lite

# Requirements specified in dag_engine_lite_impl.pyi


class DAG(dag_engine_lite.DAG):
    tier = system

    def __init__(self) -> None:
        self._nodes: Dict[str, dag_engine_lite.NodeDefinition[Any]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}

    def _find_cycle(self) -> Optional[Tuple[str, ...]]:
        """Depth-first search cycle detection with active recursion path tracking."""
        visited: Set[str] = set()
        rec_stack: List[str] = []
        in_stack: Set[str] = set()

        def dfs(u: str) -> Optional[Tuple[str, ...]]:
            visited.add(u)
            rec_stack.append(u)
            in_stack.add(u)

            # Sort neighbor nodes for deterministic cycle reporting
            for v in sorted(self._downstream.get(u, ())):
                if v in in_stack:
                    idx = rec_stack.index(v)
                    return tuple(rec_stack[idx:] + [v])
                if v not in visited:
                    res = dfs(v)
                    if res is not None:
                        return res

            rec_stack.pop()
            in_stack.remove(u)
            return None

        for node_id in sorted(self._nodes.keys()):
            if node_id not in visited:
                cycle = dfs(node_id)
                if cycle is not None:
                    return cycle

        return None

    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        """Adds a task node to the graph."""
        dep_set: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
        node_def = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=dep_set,
            priority=priority,
            retries=retries,
        )
        self._nodes[node_id] = node_def

        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()

        # Adds directed edges from each dependency to node_id, deferring existence validation
        for dep in dep_set:
            self._upstream[node_id].add(dep)
            if dep not in self._downstream:
                self._downstream[dep] = set()
            self._downstream[dep].add(node_id)

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

        self._downstream[upstream_id].add(downstream_id)
        self._upstream[downstream_id].add(upstream_id)

        # Synchronize downstream node definition dependencies
        old_def = self._nodes[downstream_id]
        if upstream_id not in old_def.dependencies:
            self._nodes[downstream_id] = dag_engine_lite.NodeDefinition(
                node_id=old_def.node_id,
                action=old_def.action,
                dependencies=old_def.dependencies | {upstream_id},
                priority=old_def.priority,
                retries=old_def.retries,
            )

        # Synchronize dynamic scheduler state
        scheduler: Any = get_singleton(dag_engine_lite.WaveScheduler)
        scheduler._sync_states()

    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )

        del self._nodes[node_id]

        # Remove node_id from incident upstream and downstream neighbor sets
        for up in list(self._upstream.get(node_id, ())):
            if up in self._downstream:
                self._downstream[up].discard(node_id)
        for down in list(self._downstream.get(node_id, ())):
            if down in self._upstream:
                self._upstream[down].discard(node_id)
            if down in self._nodes:
                old_def = self._nodes[down]
                if node_id in old_def.dependencies:
                    self._nodes[down] = dag_engine_lite.NodeDefinition(
                        node_id=old_def.node_id,
                        action=old_def.action,
                        dependencies=frozenset(d for d in old_def.dependencies if d != node_id),
                        priority=old_def.priority,
                        retries=old_def.retries,
                    )

        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

        # Purge node identifier from scheduler state
        scheduler: Any = get_singleton(dag_engine_lite.WaveScheduler)
        scheduler._purge_node(node_id)

    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph."""
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node."""
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph."""
        return set(self._nodes.keys())

    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity."""
        # Verifies that every dependency exists in _nodes
        for nid in sorted(self._nodes.keys()):
            for dep in sorted(self._nodes[nid].dependencies):
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Referenced dependency '{dep}' for node '{nid}' does not exist in graph",
                        node_id=dep,
                    )

        # Cycle detection with active recursion path tracking
        cycle = self._find_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message=f"Cycle detected: {' -> '.join(cycle)}",
                cycle=cycle,
            )

    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes."""
        # Validate that all dependencies exist
        for nid in sorted(self._nodes.keys()):
            for dep in sorted(self._nodes[nid].dependencies):
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Referenced dependency '{dep}' for node '{nid}' does not exist in graph",
                        node_id=dep,
                    )

        # In-degree counts from _upstream mapping
        in_degree: Dict[str, int] = {
            nid: len([p for p in self._upstream.get(nid, ()) if p in self._nodes])
            for nid in self._nodes
        }

        # Initializes ready list with nodes having in-degree zero, sorted by priority descending then node_id ascending
        ready: List[str] = [nid for nid, deg in in_degree.items() if deg == 0]
        ready.sort(key=lambda x: (-self._nodes[x].priority, x))

        order: List[str] = []
        while ready:
            curr = ready.pop(0)
            order.append(curr)

            # Iteratively extracts candidate with highest priority, appends to order, and decrements downstream in-degrees
            newly_ready: List[str] = []
            for down in sorted(self._downstream.get(curr, ())):
                if down in in_degree:
                    in_degree[down] -= 1
                    if in_degree[down] == 0:
                        newly_ready.append(down)

            # Inserts newly zero in-degree nodes maintaining priority descending then node_id ascending order
            for nr in newly_ready:
                ready.append(nr)
            ready.sort(key=lambda x: (-self._nodes[x].priority, x))

        # Raises CycleError containing the cycle sequence if ordered count does not equal len(_nodes)
        if len(order) != len(self._nodes):
            cycle = self._find_cycle()
            if cycle is None:  # pragma: no cover (assumption: cycle must exist when len(order) != len(_nodes))
                remaining = [nid for nid in sorted(self._nodes.keys()) if nid not in order]
                cycle = tuple(remaining + [remaining[0]]) if remaining else ()
            raise dag_engine_lite.CycleError(
                message=f"Cycle detected: {' -> '.join(cycle)}",
                cycle=cycle,
            )

        return order

    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero."""
        return {nid for nid in self._nodes if len(self._upstream.get(nid, set())) == 0}

    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero."""
        return {nid for nid in self._nodes if len(self._downstream.get(nid, set())) == 0}

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
        """Computes the longest weighted dependency path through the graph."""
        if not self._nodes:
            return ([], 0.0)

        # Computes topological order using topological_sort()
        order = self.topological_sort()

        # Resolves duration weights mapping defaulting to 1.0 for unspecified nodes
        durations: Dict[str, float] = {}
        for nid in self._nodes:
            if estimated_durations is not None and nid in estimated_durations:
                durations[nid] = float(estimated_durations[nid])
            else:
                durations[nid] = 1.0

        # Computes earliest completion times using dynamic programming
        earliest: Dict[str, float] = {}
        predecessor: Dict[str, Optional[str]] = {}

        for nid in order:
            upstream = [p for p in self._upstream.get(nid, ()) if p in self._nodes]
            if not upstream:
                earliest[nid] = durations[nid]
                predecessor[nid] = None
            else:
                # Select predecessor yielding maximum earliest time with deterministic tie-breaking
                sorted_preds = sorted(
                    upstream,
                    key=lambda x: (-earliest[x], -self._nodes[x].priority, x),
                )
                best_p = sorted_preds[0]
                earliest[nid] = earliest[best_p] + durations[nid]
                predecessor[nid] = best_p

        # Identifies terminal node with maximum completion time
        best_term: str = min(
            self._nodes.keys(),
            key=lambda x: (-earliest[x], -self._nodes[x].priority, x),
        )

        # Backtracks through upstream dependencies selecting predecessor yielding maximum earliest time
        path: List[str] = []
        curr: Optional[str] = best_term
        while curr is not None:
            path.append(curr)
            curr = predecessor.get(curr)

        path.reverse()
        total_duration = earliest[best_term]
        return (path, total_duration)


class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    def _purge_node(self, node_id: str) -> None:
        """Purges node_id from internal scheduling state."""
        self._states.pop(node_id, None)

    def _sync_states(self) -> None:
        """Synchronizes dynamic node state with registered nodes in the active DAG."""
        self._dag = get_singleton(dag_engine_lite.DAG)
        all_nodes = self._dag.all_nodes()
        # Synchronize states for nodes in DAG
        for nid in all_nodes:
            upstream = self._dag.get_dependencies(nid)
            all_satisfied = all(
                self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstream
            )
            if nid not in self._states:
                if all_satisfied:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING
            elif self._states[nid] in (
                dag_engine_lite.NodeState.READY,
                dag_engine_lite.NodeState.PENDING,
            ):
                # Unexecuted nodes dynamically synchronize to PENDING whenever unsatisfied upstream dependencies are present
                if not all_satisfied:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING
                else:
                    self._states[nid] = dag_engine_lite.NodeState.READY

    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied."""
        self._sync_states()
        ready_candidates: List[str] = []
        for nid, state in self._states.items():
            if state == dag_engine_lite.NodeState.READY:
                upstream = self._dag.get_dependencies(nid)
                if all(self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstream):
                    ready_candidates.append(nid)

        # Sort candidate nodes by definition priority descending, then node_id ascending
        ready_candidates.sort(key=lambda nid: (-self._dag.get_node(nid).priority, nid))
        return ready_candidates

    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        for dep in sorted(self._dag.get_dependents(node_id)):
            if dep in self._states and self._states[dep] == dag_engine_lite.NodeState.PENDING:
                upstream = self._dag.get_dependencies(dep)
                if all(self._states.get(u) == dag_engine_lite.NodeState.SUCCEEDED for u in upstream):
                    self._states[dep] = dag_engine_lite.NodeState.READY

    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies."""
        self._sync_states()
        self._states[node_id] = dag_engine_lite.NodeState.FAILED

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Transitions all non-terminal nodes to CANCELLED
            for nid in list(self._states.keys()):
                if self._states[nid] in (
                    dag_engine_lite.NodeState.PENDING,
                    dag_engine_lite.NodeState.READY,
                    dag_engine_lite.NodeState.RUNNING,
                ):
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            # Traverses transitive downstream dependents and marks non-terminal dependents as SKIPPED
            queue = list(self._dag.get_dependents(node_id))
            visited: Set[str] = set()
            while queue:
                dep = queue.pop(0)
                if dep not in visited:
                    visited.add(dep)
                    for nxt in self._dag.get_dependents(dep):
                        queue.append(nxt)

            for dep in visited:
                if dep in self._states and self._states[dep] in (
                    dag_engine_lite.NodeState.PENDING,
                    dag_engine_lite.NodeState.READY,
                    dag_engine_lite.NodeState.RUNNING,
                ):
                    self._states[dep] = dag_engine_lite.NodeState.SKIPPED

    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states."""
        self._sync_states()
        all_nodes = self._dag.all_nodes()
        if not all_nodes:
            return True

        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        # Check whether every node in the DAG is present in _states and in a terminal state
        return all(self._states.get(n) in terminal_states for n in all_nodes)

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node."""
        self._sync_states()
        if node_id not in self._states:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduler state",
                node_id=node_id,
            )
        return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph."""
        self._sync_states()
        all_nodes = self._dag.all_nodes()
        return {k: v for k, v in self._states.items() if k in all_nodes}


class DAGRunner(dag_engine_lite.DAGRunner):
    tier = system

    def __init__(self) -> None:
        self._dag: dag_engine_lite.DAG = get_singleton(dag_engine_lite.DAG)
        self._scheduler: dag_engine_lite.WaveScheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        """Executes the entire DAG sequentially to completion or failure."""
        self._dag = get_singleton(dag_engine_lite.DAG)
        self._scheduler = get_singleton(dag_engine_lite.WaveScheduler)
        self._results = {}

        # Validates _dag using _dag.validate(), allowing cycle or missing dependency exceptions to raise immediately
        self._dag.validate()

        start_time = time.monotonic()

        # Loops while _scheduler.is_finished() returns False and retrieves the next wave
        while not self._scheduler.is_finished():
            wave = self._scheduler.next_wave()
            if not wave:  # pragma: no cover (assumption: next_wave is non-empty while is_finished is False)
                break

            wave_failed = False
            for node_id in wave:
                node_def = self._dag.get_node(node_id)
                self._scheduler.mark_running(node_id)
                node_start = time.monotonic()

                retries_attempted = 0
                max_retries = node_def.retries
                last_error: Optional[Exception] = None
                succeeded = False
                result_val: Any = None

                while True:
                    try:
                        result_val = node_def.action()
                        succeeded = True
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        last_error = exc
                        if retries_attempted < max_retries:
                            retries_attempted += 1
                            continue
                        else:
                            succeeded = False
                            break

                duration = time.monotonic() - node_start

                if succeeded:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=result_val,
                        error=None,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_succeeded(node_id)
                else:
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=last_error,
                        duration_seconds=duration,
                        retries_attempted=retries_attempted,
                    )
                    self._scheduler.mark_failed(node_id, failure_policy=failure_policy)
                    wave_failed = True
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        break

            if wave_failed and failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                break

        # Populates _results with default unexecuted NodeResult records for terminal skipped or cancelled nodes
        for nid in sorted(self._dag.all_nodes()):
            if nid not in self._results:
                state = self._scheduler.get_state(nid)
                self._results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=state,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        # Computes critical path using _dag.compute_critical_path()
        cp_nodes, _ = self._dag.compute_critical_path()
        wall_clock = time.monotonic() - start_time

        all_nodes_sorted = sorted(self._dag.all_nodes())
        succeeded_nodes = tuple(
            n for n in all_nodes_sorted if self._results[n].state == dag_engine_lite.NodeState.SUCCEEDED
        )
        failed_nodes = tuple(
            n for n in all_nodes_sorted if self._results[n].state == dag_engine_lite.NodeState.FAILED
        )
        skipped_nodes = tuple(
            n for n in all_nodes_sorted if self._results[n].state == dag_engine_lite.NodeState.SKIPPED
        )
        cancelled_nodes = tuple(
            n for n in all_nodes_sorted if self._results[n].state == dag_engine_lite.NodeState.CANCELLED
        )

        return dag_engine_lite.DAGRunReport(
            total_nodes=len(all_nodes_sorted),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(cp_nodes),
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
# LAST_CLEANED: 2026-10-29T00:07:19Z
# LAST_CHANGED: 2026-10-29T00:04:54Z
# CHANGE: Eliminate defensive and unreachable branches in _find_cycle, add_edge, remove_node, validate, _sync_states, and is_finished, annotating impossible branches with pragma
# PRETENSE_COVERAGE_AUDIT: 2026-10-29T00:07:19Z
# PRETENSE_QA_AUDIT: 2026-10-29T00:06:27Z
# --- END CLEANROOM METADATA ---
