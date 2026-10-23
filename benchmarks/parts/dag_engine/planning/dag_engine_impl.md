# dag_engine_impl implementation component

## Intent

Concrete realization of the DAG execution engine requires thread-safe adjacency data structures, cycle detection via depth-first traversal, deterministic priority-driven topological ordering, wave-based state promotion, and bounded worker thread execution. The dag_engine_impl implementation component implements these capabilities as concrete classes realizing the dag_engine interface.

By encapsulating adjacency index management under re-entrant locks, employing Kahn's algorithm for deterministic topological scheduling, and using worker pools to manage concurrency and timeouts, the component provides robust task graph execution.

## Factored Contracts

### Typing

- A concrete directed acyclic graph maintains an internal node registry, upstream prerequisite map, downstream dependent map, and synchronization lock.
- A concrete wave scheduler maintains graph references, state tracking maps, and synchronization locks.
- A concrete DAG runner manages graph references, wave schedulers, cancellation events, and results mappings.

### Contracts

- A concrete DAG maintains node definitions in a dictionary registry synchronized by re-entrant locks. [maintain_node_registry]
- A concrete DAG maintains bidirectional adjacency dictionaries for upstream prerequisites and downstream dependents. [maintain_adjacency_maps]
- A concrete DAG verifies node presence before adding edges or removing nodes, raising node not found error if absent. [enforce_node_presence]
- A concrete DAG validates acyclicity using depth-first search path tracking and raises cycle error upon encountering a cycle. [detect_graph_cycles]
- A concrete DAG computes topological sort using in-degree tracking and a priority queue ordered by descending priority and ascending name. [execute_deterministic_topological_sort]
- A concrete DAG computes critical paths using dynamic programming over topological order with duration weights and backtracks the longest path. [compute_critical_path_dp]
- A concrete wave scheduler dynamically synchronizes node states with graph node definitions, initializing root nodes to ready state and remaining nodes to pending state. [initialize_scheduler_states]
- A concrete wave scheduler filters ready nodes whose upstream dependencies are succeeded, ordering them by priority descending. [filter_and_order_ready_wave]
- A concrete wave scheduler promotes pending dependents to ready when all upstream prerequisites transition to succeeded. [promote_unblocked_dependents]
- A concrete wave scheduler applies fail fast by cancelling all non-terminal nodes upon a node failure. [apply_fail_fast_cancellation]
- A concrete wave scheduler applies skip downstream by marking transitive dependents skipped upon a node failure. [apply_skip_downstream_marking]
- A concrete wave scheduler applies continue on error by leaving independent nodes eligible upon a node failure. [apply_continue_on_error_retention]
- A concrete wave scheduler verifies that all registered graph nodes have reached terminal states or the graph is empty. [verify_scheduler_completion]
- A concrete DAG runner validates graph acyclicity before commencing wave execution. [pre_validate_graph_before_run]
- A concrete DAG runner dispatches ready waves concurrently using a thread pool executor respecting configured maximum concurrency. [dispatch_concurrent_waves]
- A concrete DAG runner executes task actions with retry backoff and compiles succeeded and failed node results. [execute_node_action_with_retries]
- A concrete DAG runner propagates failure policy to the wave scheduler when node actions fail. [propagate_runner_failure_policy]
- A concrete DAG runner checks wall clock elapsed duration against timeouts and raises DAG timeout error if exceeded. [enforce_runner_timeout]
- A concrete DAG runner inspects cancellation events between waves, aborts active tasks, and raises DAG cancelled error when cancelled. [enforce_runner_cancellation]
- A concrete DAG runner evaluates cancellation events and timeout limits sequentially as loop guards before dispatching ready waves. [enforce_runner_loop_guards]
- A concrete DAG runner compiles node results and critical path metrics into a consolidated DAG run report upon finish. [compile_dag_run_report]

### Woven Contracts

- Node registry, adjacency maps, cycle detection, topological sorting, wave state transitions, and thread pool runners coordinate to execute task graphs safely. [maintain_node_registry, maintain_adjacency_maps, enforce_node_presence, detect_graph_cycles, execute_deterministic_topological_sort, compute_critical_path_dp, initialize_scheduler_states, filter_and_order_ready_wave, promote_unblocked_dependents, apply_fail_fast_cancellation, apply_skip_downstream_marking, apply_continue_on_error_retention, verify_scheduler_completion, pre_validate_graph_before_run, dispatch_concurrent_waves, execute_node_action_with_retries, propagate_runner_failure_policy, enforce_runner_timeout, enforce_runner_cancellation, enforce_runner_loop_guards, compile_dag_run_report]

## Grounding

### Knowledge Provisions

- Concrete directed acyclic graph implementation, wave scheduler state machine, and concurrent thread pool runner in the system lifecycle tier. [concrete_dag_engine_realization]

### Inherited Deferred Requirements

- Graph data structures, topological sort algorithms, cycle detection traversal, and thread pool execution.
  - Grounded: [concrete_dag_engine_realization]

### Knowledge Requirements

- Directed acyclic graph protocol, wave scheduler, DAG runner, lifecycle states, and run report.
  - Grounded: [dag_engine: [dag_engine_core_service]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-22T01:28:31Z
LAST_CHANGED: 2026-10-22T10:20:00Z
CHANGE: Restore system lifecycle tier and specify operation-driven failure propagation contracts
SPEC_QA_AUDIT: 2026-10-22T01:28:31Z
-->
