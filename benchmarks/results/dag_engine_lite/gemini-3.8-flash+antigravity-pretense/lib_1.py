# ==============================================================================
# Cleanroom Empirical Benchmark Flight Metrics
# Flight ID: flight_20261026_172156_gemini-3_8-flash_dag_engine_lite_pretense
# Timestamp: 2026-10-26T17:21:56.668589+00:00
# Benchmark Task: dag_engine_lite
# Model: gemini-3.8-flash (Tier 2)
# Methodology: pretense
# Harness: antigravity
# Run Index: 2
#
# Telemetry Measurements:
#   Uncached Inbound Tokens: 2,072,549
#   Cached Inbound Tokens:   21,238,486
#   Outbound Tokens:         234,336
#   Total Tokens:            23,545,371
#   Financial Cost ($USD):   $0.8320
#   Wall Clock Duration:     1187.13s
#   Step Latencies (s):      []
#   Role Execution Rounds:   lib: 2, pretense: 6, pretense_coverage: 3, pretense_qa: 5 (Total: 16)
#
# Verification Outcomes:
#   Spec Linters Pass:       True
#   Pyright Errors:          0
#   Unit Tests Passed:       53
#   Unit Tests Failed:       0
#   Line Coverage:           99.0%
#   Branch Coverage:         99.0%
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

@dataclass(frozen=True)
class DAGError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class CycleError(DAGError):
    cycle: Tuple[str, ...]


@dataclass(frozen=True)
class NodeNotFoundError(DAGError):
    node_id: str


@dataclass(frozen=True)
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
# LAST_CLEANED: 2026-10-26T17:23:23Z
# LAST_CHANGED: 2026-10-26T17:23:23Z
# CHANGE: Initialize dag_engine_lite interface module
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

    def add_node(
        self,
        node_id: str,
        action: Callable[[], Any],
        dependencies: Optional[Collection[str]] = None,
        priority: int = 0,
        retries: int = 0,
    ) -> None:
        # Constructs immutable dag_engine_lite.NodeDefinition with frozen dependency set
        frozen_deps: FrozenSet[str] = frozenset(dependencies) if dependencies is not None else frozenset()
        node_def = dag_engine_lite.NodeDefinition(
            node_id=node_id,
            action=action,
            dependencies=frozen_deps,
            priority=priority,
            retries=retries,
        )
        # Inserts definition into _nodes, registering empty neighbor sets in _upstream and _downstream if absent
        self._nodes[node_id] = node_def
        if node_id not in self._upstream:
            self._upstream[node_id] = set()
        if node_id not in self._downstream:
            self._downstream[node_id] = set()

        # Adds directed edges from each dependency to node_id
        for dep in frozen_deps:
            self._upstream[node_id].add(dep)
            if dep not in self._downstream:
                self._downstream[dep] = set()
            self._downstream[dep].add(node_id)

    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        # Verifies presence of upstream_id and downstream_id in _nodes
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
        self._downstream[upstream_id].add(downstream_id)
        self._upstream[downstream_id].add(upstream_id)

    def remove_node(self, node_id: str) -> None:
        # Verifies presence of node_id in _nodes
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        # Removes node_id from all incident upstream and downstream neighbor sets
        for down in self._downstream.get(node_id, set()):
            if down in self._upstream:
                self._upstream[down].discard(node_id)
        for up in self._upstream.get(node_id, set()):
            if up in self._downstream:
                self._downstream[up].discard(node_id)
        # Deletes node_id from _nodes, _upstream, and _downstream
        self._nodes.pop(node_id, None)
        self._upstream.pop(node_id, None)
        self._downstream.pop(node_id, None)

    def has_node(self, node_id: str) -> bool:
        # Checks membership of node_id in _nodes
        return node_id in self._nodes

    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        # Looks up node_id in _nodes, raising NodeNotFoundError if missing
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return self._nodes[node_id]

    def get_dependencies(self, node_id: str) -> Set[str]:
        # Verifies node_id in _nodes, raising NodeNotFoundError if missing
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._upstream.get(node_id, set()))

    def get_dependents(self, node_id: str) -> Set[str]:
        # Verifies node_id in _nodes, raising NodeNotFoundError if missing
        if node_id not in self._nodes:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in DAG",
                node_id=node_id,
            )
        return set(self._downstream.get(node_id, set()))

    def all_nodes(self) -> Set[str]:
        # Returns a copy of set(_nodes.keys())
        return set(self._nodes.keys())

    def _detect_cycle(self) -> Optional[Tuple[str, ...]]:
        visited: Set[str] = set()
        rec_stack: List[str] = []
        in_rec_stack: Set[str] = set()

        def dfs(curr: str) -> Optional[Tuple[str, ...]]:
            visited.add(curr)
            rec_stack.append(curr)
            in_rec_stack.add(curr)

            for neighbor in sorted(self._downstream.get(curr, set())):
                if neighbor in self._nodes:
                    if neighbor in in_rec_stack:
                        idx = rec_stack.index(neighbor)
                        return tuple(rec_stack[idx:] + [neighbor])
                    if neighbor not in visited:
                        res = dfs(neighbor)
                        if res is not None:
                            return res

            rec_stack.pop()
            in_rec_stack.remove(curr)
            return None

        for node in sorted(self._nodes.keys()):
            if node not in visited:
                cycle = dfs(node)
                if cycle is not None:
                    return cycle
        return None

    def validate(self) -> None:
        # Verifies that every dependency in every node definition exists in _nodes
        for node_id, node_def in self._nodes.items():
            for dep in node_def.dependencies:
                if dep not in self._nodes:
                    raise dag_engine_lite.NodeNotFoundError(
                        message=f"Dependency '{dep}' referenced by node '{node_id}' does not exist in DAG",
                        node_id=dep,
                    )
        # Executes depth-first search cycle detection with active recursion path tracking
        cycle = self._detect_cycle()
        if cycle is not None:
            raise dag_engine_lite.CycleError(
                message=f"Dependency cycle detected: {' -> '.join(cycle)}",
                cycle=cycle,
            )

    def topological_sort(self) -> List[str]:
        # Computes in-degree counts from _upstream mapping
        in_degree: Dict[str, int] = {
            nid: len(self._upstream.get(nid, set()))
            for nid in self._nodes
        }
        # Initializes ready list with nodes having in-degree zero, sorted by priority descending then node_id ascending
        ready: List[str] = [nid for nid, deg in in_degree.items() if deg == 0]
        ready.sort(key=lambda nid: (-self._nodes[nid].priority, nid))

        order: List[str] = []
        # Iteratively extracts candidate with highest priority, appends to order, and decrements downstream in-degrees
        while ready:
            curr = ready.pop(0)
            order.append(curr)
            for downstream in sorted(self._downstream.get(curr, set())):
                if downstream in in_degree:
                    in_degree[downstream] -= 1
                    # Inserts newly zero in-degree nodes maintaining priority descending then node_id ascending order
                    if in_degree[downstream] == 0:
                        ready.append(downstream)
                        ready.sort(key=lambda nid: (-self._nodes[nid].priority, nid))

        # Raises CycleError containing the cycle sequence if ordered count does not equal len(_nodes)
        if len(order) != len(self._nodes):
            cycle = self._detect_cycle()
            cycle_seq = cycle if cycle is not None else ()  # pragma: no cover (assumption: Kahn algorithm failure implies directed cycle exists)
            raise dag_engine_lite.CycleError(
                message=f"Dependency cycle detected in topological sort: {' -> '.join(cycle_seq)}",
                cycle=cycle_seq,
            )

        return order

    def find_roots(self) -> Set[str]:
        # Iterates over _nodes, collecting node identifiers whose _upstream set is empty
        return {nid for nid in self._nodes if len(self._upstream.get(nid, set())) == 0}

    def find_leaves(self) -> Set[str]:
        # Iterates over _nodes, collecting node identifiers whose _downstream set is empty
        return {nid for nid in self._nodes if len(self._downstream.get(nid, set())) == 0}

    def compute_critical_path(
        self,
        estimated_durations: Optional[Mapping[str, float]] = None,
    ) -> Tuple[List[str], float]:
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
        best_pred: Dict[str, Optional[str]] = {}

        for nid in order:
            preds = sorted(p for p in self._upstream.get(nid, set()) if p in earliest)
            if preds:
                chosen_p = max(preds, key=lambda p: earliest[p])
                earliest[nid] = earliest[chosen_p] + durations[nid]
                best_pred[nid] = chosen_p
            else:
                earliest[nid] = durations[nid]
                best_pred[nid] = None

        # Identifies terminal node with maximum completion time
        terminal_node = max(sorted(self._nodes.keys()), key=lambda n: earliest[n])
        max_time = earliest[terminal_node]

        # Backtracks through upstream dependencies selecting predecessor yielding maximum earliest time
        path: List[str] = []
        curr: Optional[str] = terminal_node
        while curr is not None:
            path.append(curr)
            curr = best_pred.get(curr)
        path.reverse()

        return (path, max_time)


class WaveScheduler(dag_engine_lite.WaveScheduler):
    tier = system

    def __init__(self) -> None:
        self._states: Dict[str, dag_engine_lite.NodeState] = {}

    @property
    def _dag(self) -> dag_engine_lite.DAG:
        return get_singleton(dag_engine_lite.DAG)

    def _sync_states(self) -> None:
        # Synchronizes dynamic node state by discovering registered nodes from _dag.all_nodes()
        dag = self._dag
        dag_nodes = dag.all_nodes()
        for nid in dag_nodes:
            if nid not in self._states:
                deps = dag.get_dependencies(nid)
                if not deps:
                    self._states[nid] = dag_engine_lite.NodeState.READY
                else:
                    self._states[nid] = dag_engine_lite.NodeState.PENDING
        for nid in list(self._states.keys()):
            if nid not in dag_nodes:
                del self._states[nid]

    def next_wave(self) -> List[str]:
        # Ensures _states contains all nodes from _dag, initializing roots to READY and non-roots to PENDING
        self._sync_states()
        dag = self._dag
        candidates: List[str] = []
        for nid, st in self._states.items():
            # Gathers all nodes currently in READY state whose upstream dependencies are all SUCCEEDED
            if st == dag_engine_lite.NodeState.READY:
                deps = dag.get_dependencies(nid)
                if all(self._states.get(dep) == dag_engine_lite.NodeState.SUCCEEDED for dep in deps):
                    candidates.append(nid)

        # Sorts candidate nodes by definition priority descending, then node_id ascending
        candidates.sort(key=lambda nid: (-dag.get_node(nid).priority, nid))
        return candidates

    def mark_running(self, node_id: str) -> None:
        self._sync_states()
        # Sets _states[node_id] to RUNNING
        self._states[node_id] = dag_engine_lite.NodeState.RUNNING

    def mark_succeeded(self, node_id: str) -> None:
        self._sync_states()
        # Sets _states[node_id] to SUCCEEDED
        self._states[node_id] = dag_engine_lite.NodeState.SUCCEEDED
        dag = self._dag
        # Inspects downstream dependents of node_id
        for dependent_id in dag.get_dependents(node_id):
            if self._states.get(dependent_id) == dag_engine_lite.NodeState.PENDING:
                upstream_deps = dag.get_dependencies(dependent_id)
                # Promotes any dependent currently in PENDING to READY if all its upstream dependencies are SUCCEEDED
                if all(self._states.get(dep) == dag_engine_lite.NodeState.SUCCEEDED for dep in upstream_deps):
                    self._states[dependent_id] = dag_engine_lite.NodeState.READY

    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        self._sync_states()
        # Sets _states[node_id] to FAILED
        self._states[node_id] = dag_engine_lite.NodeState.FAILED
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }

        if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
            # Transitions all non-terminal nodes to CANCELLED if failure_policy is FAIL_FAST
            for nid, st in list(self._states.items()):
                if nid != node_id and st not in terminal_states:
                    self._states[nid] = dag_engine_lite.NodeState.CANCELLED
        elif failure_policy in (
            dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM,
            dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR,
        ):
            dag = self._dag
            # Traverses transitive downstream dependents and marks non-terminal dependents as SKIPPED
            transitive: Set[str] = set()
            queue = list(dag.get_dependents(node_id))
            while queue:
                curr = queue.pop(0)
                if curr not in transitive:
                    transitive.add(curr)
                    queue.extend(dag.get_dependents(curr))
            for dep_id in transitive:
                if self._states.get(dep_id) not in terminal_states:
                    self._states[dep_id] = dag_engine_lite.NodeState.SKIPPED

    def is_finished(self) -> bool:
        # Synchronizes _states with all nodes currently registered in _dag.all_nodes()
        self._sync_states()
        dag = self._dag
        nodes = dag.all_nodes()
        if not nodes:
            return True
        terminal_states = {
            dag_engine_lite.NodeState.SUCCEEDED,
            dag_engine_lite.NodeState.FAILED,
            dag_engine_lite.NodeState.SKIPPED,
            dag_engine_lite.NodeState.CANCELLED,
        }
        # Checks whether every node in the DAG is present in _states and in a terminal state
        return all(self._states.get(nid) in terminal_states for nid in nodes)

    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        # Ensures _states contains node_id by synchronizing with _dag.all_nodes() if absent
        self._sync_states()
        if node_id not in self._states:
            raise dag_engine_lite.NodeNotFoundError(
                message=f"Node '{node_id}' not found in scheduler",
                node_id=node_id,
            )
        return self._states[node_id]

    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        # Ensures _states contains all nodes from _dag.all_nodes()
        self._sync_states()
        return dict(self._states)


class DAGRunner(dag_engine_lite.DAGRunner):
    tier = system

    def __init__(self) -> None:
        self._results: Dict[str, dag_engine_lite.NodeResult[Any]] = {}

    @property
    def _dag(self) -> dag_engine_lite.DAG:
        return get_singleton(dag_engine_lite.DAG)

    @property
    def _scheduler(self) -> dag_engine_lite.WaveScheduler:
        return get_singleton(dag_engine_lite.WaveScheduler)

    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> dag_engine_lite.DAGRunReport:
        dag = self._dag
        scheduler = self._scheduler

        # Validates _dag using _dag.validate(), allowing cycle or missing dependency exceptions to raise immediately
        dag.validate()

        start_time = time.perf_counter()
        self._results = {}

        # Loops while _scheduler.is_finished() returns False and retrieves the next wave from _scheduler.next_wave()
        while not scheduler.is_finished():
            wave = scheduler.next_wave()
            # Halts wave loop when next wave is empty
            if not wave:  # pragma: no cover (assumption: verified acyclic DAG guarantees ready nodes until finished)
                break

            wave_failed = False
            for node_id in wave:
                # Dispatches each ready wave node sequentially, marking it RUNNING in _scheduler
                scheduler.mark_running(node_id)
                node_def = dag.get_node(node_id)
                retries_done = 0
                last_error: Optional[Exception] = None
                action_value: Any = None
                node_start = time.perf_counter()
                node_success = False

                # Executes node action with retry attempts up to definition.retries upon exception
                for attempt in range(node_def.retries + 1):
                    try:
                        action_value = node_def.action()
                        node_success = True
                        break
                    except Exception as exc:  # cleanroom: allow-broad-exception
                        last_error = exc
                        if attempt < node_def.retries:
                            retries_done += 1

                node_duration = time.perf_counter() - node_start

                if node_success:
                    # Records dag_engine_lite.NodeResult(SUCCEEDED) and marks SUCCEEDED in _scheduler on success
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.SUCCEEDED,
                        value=action_value,
                        error=None,
                        duration_seconds=node_duration,
                        retries_attempted=retries_done,
                    )
                    scheduler.mark_succeeded(node_id)
                else:
                    # Records dag_engine_lite.NodeResult(FAILED) and marks FAILED in _scheduler with failure_policy on failure after retries
                    self._results[node_id] = dag_engine_lite.NodeResult(
                        node_id=node_id,
                        state=dag_engine_lite.NodeState.FAILED,
                        value=None,
                        error=last_error,
                        duration_seconds=node_duration,
                        retries_attempted=retries_done,
                    )
                    scheduler.mark_failed(node_id, failure_policy)
                    # Halts further wave execution when failure_policy is FAIL_FAST and a node has failed
                    if failure_policy == dag_engine_lite.FailurePolicy.FAIL_FAST:
                        wave_failed = True
                        break

            if wave_failed:
                break

        # Populates _results with default unexecuted dag_engine_lite.NodeResult records for terminal skipped or cancelled nodes from _scheduler states
        all_states = scheduler.get_all_states()
        for nid in sorted(dag.all_nodes()):
            if nid not in self._results:
                st = all_states.get(nid, dag_engine_lite.NodeState.SKIPPED)
                self._results[nid] = dag_engine_lite.NodeResult(
                    node_id=nid,
                    state=st,
                    value=None,
                    error=None,
                    duration_seconds=0.0,
                    retries_attempted=0,
                )

        # Computes critical path using _dag.compute_critical_path()
        crit_path, _ = dag.compute_critical_path()
        wall_clock = time.perf_counter() - start_time

        # Gathers succeeded, failed, skipped, and cancelled node tuples from _results and _scheduler states
        succeeded_nodes = tuple(nid for nid, res in self._results.items() if res.state == dag_engine_lite.NodeState.SUCCEEDED)
        failed_nodes = tuple(nid for nid, res in self._results.items() if res.state == dag_engine_lite.NodeState.FAILED)
        skipped_nodes = tuple(nid for nid, res in self._results.items() if res.state == dag_engine_lite.NodeState.SKIPPED)
        cancelled_nodes = tuple(nid for nid, res in self._results.items() if res.state == dag_engine_lite.NodeState.CANCELLED)

        # Returns consolidated dag_engine_lite.DAGRunReport
        return dag_engine_lite.DAGRunReport(
            total_nodes=len(dag.all_nodes()),
            succeeded_nodes=succeeded_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            cancelled_nodes=cancelled_nodes,
            wall_clock_seconds=wall_clock,
            critical_path=tuple(crit_path),
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
# LAST_CLEANED: 2026-10-26T17:41:43Z
# LAST_CHANGED: 2026-10-26T17:35:00Z
# CHANGE: Eliminate unreachable singleton attribute branches in WaveScheduler and DAGRunner using properties, and annotate defensive break in DAGRunner.run with pragma
# PRETENSE_COVERAGE_AUDIT: 2026-10-26T17:41:43Z
# PRETENSE_QA_AUDIT: 2026-10-26T17:41:08Z
# --- END CLEANROOM METADATA ---
