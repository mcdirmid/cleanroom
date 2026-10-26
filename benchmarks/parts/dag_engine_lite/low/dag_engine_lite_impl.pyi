"""Low-level implementation specification for the synchronous DAG execution and wave scheduling engine."""

from __future__ import annotations

from typing import Any, Callable, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
from support.lib.framework import operation, override, singleton_type
from support.lib.lifecycle import Singleton, SystemTier, get_singleton
import dag_engine_lite


@singleton_type("system")
class DAG(dag_engine_lite.DAG):
    """Concrete realization of the Directed Acyclic Graph.

    GROUNDING:
    - Maintains adjacency dictionaries _nodes, _upstream, and _downstream mapping node identifiers to definitions and sets.
    """

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
        """Adds a task node to the graph.

        GROUNDING:
        - Constructs immutable dag_engine_lite.NodeDefinition with frozen dependency set without eagerly checking dependency existence.
        - Inserts definition into _nodes, registering empty neighbor sets in _upstream and _downstream if absent.
        - Adds directed edges from each dependency to node_id, deferring existence validation.
        """
        ...

    @operation
    @override
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        GROUNDING:
        - Verifies presence of upstream_id and downstream_id in _nodes.
        - Raises dag_engine_lite.NodeNotFoundError if either identifier is missing.
        - Updates _upstream and _downstream sets.
        """
        ...

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
        ...

    @operation
    @override
    def has_node(self, node_id: str) -> bool:
        """Checks whether a node exists within the graph.

        GROUNDING:
        - Checks membership of node_id in _nodes.
        """
        ...

    @operation
    @override
    def get_node(self, node_id: str) -> dag_engine_lite.NodeDefinition[Any]:
        """Retrieves the immutable definition of a registered node.

        GROUNDING:
        - Looks up node_id in _nodes.
        - Raises dag_engine_lite.NodeNotFoundError if node_id is not present.
        """
        ...

    @operation
    @override
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        GROUNDING:
        - Verifies node_id in _nodes, raising dag_engine_lite.NodeNotFoundError if missing.
        - Returns a copy of _upstream[node_id].
        """
        ...

    @operation
    @override
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        GROUNDING:
        - Verifies node_id in _nodes, raising dag_engine_lite.NodeNotFoundError if missing.
        - Returns a copy of _downstream[node_id].
        """
        ...

    @operation
    @override
    def all_nodes(self) -> Set[str]:
        """Returns all node identifiers present in the graph.

        GROUNDING:
        - Returns a copy of set(_nodes.keys()).
        """
        ...

    @operation
    @override
    def validate(self) -> None:
        """Validates graph consistency, completeness, and acyclicity.

        GROUNDING:
        - Verifies that every dependency in every node definition exists in _nodes, raising dag_engine_lite.NodeNotFoundError if missing.
        - Executes depth-first search cycle detection with active recursion path tracking.
        - Raises dag_engine_lite.CycleError containing the cycle sequence upon detecting any directed cycle.
        """
        ...

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
        ...

    @operation
    @override
    def find_roots(self) -> Set[str]:
        """Returns all root nodes with in-degree zero.

        GROUNDING:
        - Iterates over _nodes, collecting node identifiers whose _upstream set is empty.
        - Returns set of root node identifiers.
        """
        ...

    @operation
    @override
    def find_leaves(self) -> Set[str]:
        """Returns all leaf nodes with out-degree zero.

        GROUNDING:
        - Iterates over _nodes, collecting node identifiers whose _downstream set is empty.
        - Returns set of leaf node identifiers.
        """
        ...

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
        ...


@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.

    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states dictionary mapping node identifiers to dag_engine_lite.NodeState.
    - Synchronizes dynamic node state by discovering registered nodes from _dag.all_nodes(), initializing root nodes to dag_engine_lite.NodeState.READY and non-root nodes to dag_engine_lite.NodeState.PENDING.
    """

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
        ...

    @operation
    @override
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        GROUNDING:
        - Sets _states[node_id] to dag_engine_lite.NodeState.RUNNING.
        """
        ...

    @operation
    @override
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        GROUNDING:
        - Sets _states[node_id] to dag_engine_lite.NodeState.SUCCEEDED.
        - Inspects downstream dependents of node_id.
        - Promotes any dependent currently in dag_engine_lite.NodeState.PENDING to dag_engine_lite.NodeState.READY if all its upstream dependencies are dag_engine_lite.NodeState.SUCCEEDED.
        """
        ...

    @operation
    @override
    def mark_failed(
        self,
        node_id: str,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
    ) -> None:
        """Transitions a node to the FAILED state and applies failure policies.

        GROUNDING:
        - Sets _states[node_id] to dag_engine_lite.NodeState.FAILED.
        - Transitions all non-terminal nodes to dag_engine_lite.NodeState.CANCELLED if failure_policy is dag_engine_lite.FailurePolicy.FAIL_FAST.
        - Traverses transitive downstream dependents and marks non-terminal dependents as dag_engine_lite.NodeState.SKIPPED if failure_policy is dag_engine_lite.FailurePolicy.SKIP_DOWNSTREAM.
        - Retains non-terminal states for unblocked independent nodes if failure_policy is dag_engine_lite.FailurePolicy.CONTINUE_ON_ERROR, transitioning blocked dependents of failed nodes to dag_engine_lite.NodeState.SKIPPED.
        """
        ...

    @operation
    @override
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        GROUNDING:
        - Synchronizes _states with all nodes currently registered in _dag.all_nodes().
        - Checks whether every node in the DAG is present in _states and in a terminal state (SUCCEEDED, FAILED, SKIPPED, CANCELLED).
        - Returns True if all registered DAG nodes have reached terminal states or if no ready nodes remain and unexecuted nodes are blocked by failed dependencies, or if DAG is empty; False otherwise.
        """
        ...

    @operation
    @override
    def get_state(self, node_id: str) -> dag_engine_lite.NodeState:
        """Retrieves the current execution state of a node.

        GROUNDING:
        - Ensures _states contains node_id by synchronizing with _dag.all_nodes() if absent.
        - Returns _states[node_id].
        """
        ...

    @operation
    @override
    def get_all_states(self) -> Mapping[str, dag_engine_lite.NodeState]:
        """Returns the execution state of every node in the graph.

        GROUNDING:
        - Ensures _states contains all nodes from _dag.all_nodes().
        - Returns a shallow copy of _states mapping filtered to only include nodes currently present in _dag.all_nodes().
        """
        ...


@singleton_type("system")
class DAGRunner(dag_engine_lite.DAGRunner):
    """Concrete realization of sequential DAG execution runner.

    GROUNDING:
    - Resolves active DAG service via get_singleton(dag_engine_lite.DAG) and WaveScheduler service via get_singleton(dag_engine_lite.WaveScheduler).
    - Coordinates execution using _dag, _scheduler, and _results mapping.
    """

    @operation
    @override
    def run(
        self,
        failure_policy: dag_engine_lite.FailurePolicy = dag_engine_lite.FailurePolicy.FAIL_FAST,
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
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T20:55:00Z
# LAST_CHANGED: 2026-10-26T20:55:00Z
# CHANGE: Specify dynamic scheduler state synchronization on remove_node, ascending alphabetical tie-breaking, and SKIP state for blocked dependents
# SPEC_QA_AUDIT: 2026-10-26T20:55:00Z
# --- END CLEANROOM METADATA ---
