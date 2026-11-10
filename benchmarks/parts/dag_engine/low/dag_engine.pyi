"""Low-level specification for the DAG execution and wave scheduling engine."""

from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Any, Callable, Collection, FrozenSet, Generic, List, Mapping, Optional, Protocol, Sequence, Set, Tuple, TypeVar
from support.lib.framework import data_type, operation, singleton_type
from support.lib.lifecycle import Singleton, SystemTier
from pretense import test_only

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


@data_type
@dataclass(frozen=True)
class DAGTimeoutError(DAGError):
    """Raised when overall DAG execution exceeds the allocated timeout."""
    ...


@data_type
@dataclass(frozen=True)
class DAGCancelledError(DAGError):
    """Raised when DAG execution is explicitly cancelled."""
    ...


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
        timeout_seconds: Optional timeout in seconds for this node action.
        retries: Number of retry attempts on failure.
    """
    node_id: str
    action: Callable[[], T]
    dependencies: FrozenSet[str]
    priority: int = 0
    timeout_seconds: Optional[float] = None
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
        timeout_seconds: Optional[float],
        retries: int,
    ) -> None:
        """Adds a task node to the graph.

        Args:
            node_id: Unique string identifier for the node.
            action: Zero-argument callable representing node computation.
            dependencies: Optional collection of upstream node identifiers.
            priority: Scheduling priority (higher executes earlier).
            timeout_seconds: Optional per-node execution timeout.
            retries: Number of permitted retry attempts upon exception.

        POSTCONDITIONS:
        - [slug:dag.dag.add_node.register_definition]: MUST register the node definition into the graph.
        - [slug:dag.dag.add_node.directed_dependencies]: WHEN dependencies are provided, MUST add directed dependency edges from each dependency to node_id.
        """
        ...

    @operation
    def add_edge(self, upstream_id: str, downstream_id: str) -> None:
        """Adds a directed dependency edge where downstream depends on upstream.

        Args:
            upstream_id: Identifier of the prerequisite node.
            downstream_id: Identifier of the dependent node.

        Raises:
            NodeNotFoundError: If either node identifier is missing from the graph.

        PRECONDITIONS:
        - [slug:dag.dag.add_edge.nodes_must_exist]: WHEN upstream_id or downstream_id does not exist, MUST raise NodeNotFoundError.

        POSTCONDITIONS:
        - [slug:dag.dag.add_edge.directed_edge]: MUST establish a directed dependency edge from upstream_id to downstream_id.
        """
        ...

    @operation
    def remove_node(self, node_id: str) -> None:
        """Removes a node and all incident dependency edges from the graph.

        Args:
            node_id: Identifier of the node to remove.

        Raises:
            NodeNotFoundError: If node_id does not exist in the graph.

        PRECONDITIONS:
        - [slug:dag.dag.remove_node.node_must_exist]: WHEN node_id is absent, MUST raise NodeNotFoundError.

        POSTCONDITIONS:
        - [slug:dag.dag.remove_node.purge_incident_edges]: MUST remove the node and its incident edges.
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

        Raises:
            NodeNotFoundError: If node_id is not in the graph.

        PRECONDITIONS:
        - [slug:dag.dag.get_node.node_must_exist]: WHEN node_id is absent, MUST raise NodeNotFoundError.

        POSTCONDITIONS:
        - [slug:dag.dag.get_node.return_definition]: MUST return the NodeDefinition matching node_id.
        """
        ...

    @operation
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Returns direct upstream dependency identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of upstream node identifiers.

        Raises:
            NodeNotFoundError: If node_id is not in the graph.

        PRECONDITIONS:
        - [slug:dag.dag.get_dependencies.node_must_exist]: WHEN node_id is absent, MUST raise NodeNotFoundError.

        POSTCONDITIONS:
        - [slug:dag.dag.get_dependencies.return_upstream]: MUST return all direct upstream dependencies.
        """
        ...

    @operation
    def get_dependents(self, node_id: str) -> Set[str]:
        """Returns direct downstream dependent identifiers for a node.

        Args:
            node_id: Identifier of the node.

        Returns:
            Set of downstream node identifiers.

        Raises:
            NodeNotFoundError: If node_id is not in the graph.

        PRECONDITIONS:
        - [slug:dag.dag.get_dependents.node_must_exist]: WHEN node_id is absent, MUST raise NodeNotFoundError.

        POSTCONDITIONS:
        - [slug:dag.dag.get_dependents.return_downstream]: MUST return all direct downstream dependents.
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
        """Validates graph consistency, completeness, and acyclicity.

        Raises:
            NodeNotFoundError: If any node references a dependency not in the graph.
            CycleError: If any directed cycle exists in the graph.

        PRECONDITIONS:
        - [slug:dag.dag.validate.dependencies_exist]: WHEN a dependency node is missing, MUST raise NodeNotFoundError.
        - [slug:dag.dag.validate.acyclic_graph]: WHEN a cycle exists, MUST raise CycleError containing the cycle sequence.

        POSTCONDITIONS:
        - [slug:dag.dag.validate.complete_valid]: WHEN all referenced nodes exist and no cycle exists, MUST complete without error.
        """
        ...

    @operation
    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological ordering of all nodes.

        Tie-breaking between independent nodes is resolved first by priority (descending),
        then alphabetically by node_id (ascending).

        Returns:
            List of node identifiers in topological order.

        Raises:
            CycleError: If the graph contains a directed cycle.

        PRECONDITIONS:
        - [slug:dag.dag.topological_sort.acyclic_graph]: WHEN a cycle exists, MUST raise CycleError.

        POSTCONDITIONS:
        - [slug:dag.dag.topological_sort.dependency_order]: MUST return a valid topological ordering where every prerequisite precedes its dependents.
        - [slug:dag.dag.topological_sort.tie_breaking]: MUST break ties between concurrent ready nodes using priority descending and name ascending.
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

        POSTCONDITIONS:
        - [slug:dag.dag.critical_path.longest_path]: MUST return the sequence of nodes that forms the longest path through the DAG.
        - [slug:dag.dag.critical_path.cumulative_weight]: MUST return the cumulative weight of that path.
        """
        ...


@singleton_type("system")
class WaveScheduler(Singleton[SystemTier], Protocol):
    """Partitions and coordinates DAG nodes into executable waves of concurrency."""

    @operation
    def next_wave(self) -> List[str]:
        """Resolves the next batch of ready nodes whose dependencies are satisfied.

        Returns:
            List of node identifiers ready for concurrent execution, ordered by priority descending.

        POSTCONDITIONS:
        - [slug:dag.scheduler.next_wave.ready_nodes]: MUST return all nodes currently in READY state whose upstream dependencies are SUCCEEDED.
        - [slug:dag.scheduler.next_wave.priority_order]: MUST order returned nodes by priority descending, then node_id ascending.
        - [slug:dag.scheduler.next_wave.empty_when_no_ready]: WHEN no nodes are ready, MUST return an empty list.
        """
        ...

    @operation
    def mark_running(self, node_id: str) -> None:
        """Transitions a node to the RUNNING state.

        Args:
            node_id: Identifier of the executing node.

        POSTCONDITIONS:
        - [slug:dag.scheduler.mark_running.state_transition]: MUST update the node state to RUNNING.
        """
        ...

    @operation
    def mark_succeeded(self, node_id: str) -> None:
        """Transitions a node to the SUCCEEDED state and unlocks downstream dependents.

        Args:
            node_id: Identifier of the completed node.

        POSTCONDITIONS:
        - [slug:dag.scheduler.mark_succeeded.state_transition]: MUST update the node state to SUCCEEDED.
        - [slug:dag.scheduler.mark_succeeded.promote_dependents]: MUST evaluate downstream dependents and promote newly unblocked nodes to READY.
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

        POSTCONDITIONS:
        - [slug:dag.scheduler.mark_failed.state_transition]: MUST update the node state to FAILED.
        - [slug:dag.scheduler.mark_failed.skip_downstream]: WHEN failure_policy is SKIP_DOWNSTREAM, MUST transition all transitive dependents to SKIPPED.
        - [slug:dag.scheduler.mark_failed.fail_fast]: WHEN failure_policy is FAIL_FAST, MUST transition all remaining PENDING nodes to CANCELLED.
        - [slug:dag.scheduler.mark_failed.continue_on_error]: WHEN failure_policy is CONTINUE_ON_ERROR, MUST leave unblocked independent nodes eligible for execution.
        """
        ...

    @operation
    def is_finished(self) -> bool:
        """Determines whether all nodes have reached terminal states.

        Returns:
            True if all nodes in the DAG have reached terminal states.

        POSTCONDITIONS:
        - [slug:dag.scheduler.is_finished.all_terminal]: WHEN all nodes in the DAG have reached terminal states (SUCCEEDED, FAILED, SKIPPED, CANCELLED), MUST return True.
        - [slug:dag.scheduler.is_finished.non_terminal_remaining]: WHEN any node in the DAG is not in a terminal state, MUST return False.
        - [slug:dag.scheduler.is_finished.empty_dag]: WHEN the DAG contains no nodes, MUST return True.
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
            Mapping of node identifier to current NodeState.
        """
        ...


@singleton_type("system")
class DAGRunner(Singleton[SystemTier], Protocol):
    """Executes a DAG under concurrency limits, failure policies, and timeouts."""

    @operation
    def run(
        self,
        timeout_seconds: Optional[float],
        failure_policy: FailurePolicy,
        max_concurrency: int,
    ) -> DAGRunReport:
        """Executes the entire DAG to completion or failure.

        Args:
            timeout_seconds: Optional overall execution timeout in seconds.
            failure_policy: Failure policy applied upon node action failure.
            max_concurrency: Maximum number of worker threads for concurrent wave execution.

        Returns:
            Consolidated DAGRunReport recording all node outcomes and metrics.

        Raises:
            DAGTimeoutError: If execution exceeds timeout_seconds.
            DAGCancelledError: If cancel() is invoked during execution.

        PRECONDITIONS:
        - [slug:dag.runner.run.timeout_limit]: WHEN execution exceeds timeout_seconds, MUST raise DAGTimeoutError.
        - [slug:dag.runner.run.abort_on_cancel]: WHEN cancelled during execution, MUST mark running nodes as CANCELLED and raise DAGCancelledError.

        POSTCONDITIONS:
        - [slug:dag.runner.run.concurrent_execution]: MUST execute ready nodes concurrently up to the configured concurrency limit.
        - [slug:dag.runner.run.retry_failures]: MUST execute retries up to the configured retry count for failed node actions.
        - [slug:dag.runner.run.apply_failure_policy]: MUST apply the specified failure_policy to the scheduler upon node failure.
        - [slug:dag.runner.run.consolidated_report]: MUST return a DAGRunReport capturing all node states, execution durations, and critical path.
        """
        ...

    @operation
    def cancel(self) -> None:
        """Signals active execution to abort, cancelling all non-terminal nodes.

        POSTCONDITIONS:
        - [slug:dag.runner.cancel.abort_execution]: MUST set cancellation status and abort subsequent wave execution.
        """
        ...

    @operation
    @test_only
    def is_cancelled(self) -> bool:
        """Query accessor verifying whether cancellation has been signaled.

        Returns:
            True if cancellation status has been set, False otherwise.

        POSTCONDITIONS:
        - [slug:dag.runner.is_cancelled.cancelled_status]: WHEN cancel() has been called, MUST return True.
        - [slug:dag.runner.is_cancelled.active_status]: WHEN cancel() has not been called, MUST return False.
        """
        ...

# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-26T21:35:31Z
# LAST_CHANGED: 2026-11-02T19:55:00Z
# CHANGE: Add is_cancelled @test_only observability query to DAGRunner
# SPEC_QA_AUDIT: 2026-10-26T21:35:31Z
# --- END CLEANROOM METADATA ---
