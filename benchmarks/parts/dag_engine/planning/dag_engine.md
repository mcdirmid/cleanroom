# dag_engine interface component

## Intent

Asynchronous and concurrent software systems require declarative, cycle-safe graph structures to express complex task dependencies, orchestrate parallel execution waves, manage retries, handle timeouts, and isolate failures. The dag_engine interface component defines abstract protocols, data types, and lifecycle contracts for constructing Directed Acyclic Graphs, partitioning ready nodes into concurrent waves, tracking execution states, and computing critical path metrics.

By factoring graph construction, topological sorting, failure propagation policies, and execution orchestration into decoupled protocols, the component enables deterministic execution and thorough verification of concurrent task pipelines.

## Factored Contracts

### Typing

- A DAG error carries a diagnostic message.
- A cycle error carries an error message and a cycle sequence of node identifiers.
- A node not found error carries an error message and a missing node identifier.
- A node execution error carries an error message, a failed node identifier, and an underlying caught exception.
- A DAG timeout error indicates overall graph execution timeout.
- A DAG cancelled error indicates explicit graph execution cancellation.
- A node state takes the form of pending, ready, running, succeeded, failed, cancelled, or skipped.
- A failure policy takes the form of fail fast, continue on error, or skip downstream.
- A node definition carries a node identifier, a zero-argument callable action, a set of upstream dependency identifiers, a scheduling priority, an optional per-node timeout, and a permitted retry count.
- A node result carries a node identifier, a final node state, an optional returned value, an optional caught error, an elapsed duration, and an attempted retry count.
- A DAG run report carries a total node count, succeeded node identifiers, failed node identifiers, skipped node identifiers, cancelled node identifiers, a wall clock duration, a critical path sequence, and a results mapping.
- A directed acyclic graph maintains nodes and directed dependency edges.
- A wave scheduler partitions and coordinates ready nodes into concurrent execution waves.
- A DAG runner executes a graph under concurrency limits and timeouts.

### Contracts

- A directed acyclic graph registers a task node with a callable action, optional dependencies, priority, timeout, and retries. [add_node_to_graph]
- A directed acyclic graph adds a directed dependency edge between prerequisite and dependent nodes. [add_edge_between_nodes]
- When a referenced node does not exist during edge addition, node removal, or node retrieval, the graph raises node not found error. [raise_node_not_found_on_missing_reference]
- A directed acyclic graph removes a node and its incident edges. [remove_node_from_graph]
- A directed acyclic graph tests whether a node identifier exists. [test_node_presence]
- A directed acyclic graph retrieves the immutable definition of a registered node. [retrieve_node_definition]
- A directed acyclic graph retrieves direct upstream dependencies for a node. [retrieve_upstream_dependencies]
- A directed acyclic graph retrieves direct downstream dependents for a node. [retrieve_downstream_dependents]
- A directed acyclic graph lists all registered node identifiers. [list_all_graph_nodes]
- A directed acyclic graph validates that all referenced dependencies exist and raises cycle error if any directed cycle exists. [validate_graph_invariants]
- A directed acyclic graph computes a deterministic topological ordering breaking ties by descending priority then ascending node identifier. [compute_topological_sort]
- When a cycle is detected during topological sort or validation, the graph raises cycle error containing the cycle sequence. [raise_cycle_error_on_directed_cycle]
- A directed acyclic graph identifies root nodes having zero dependencies. [find_graph_roots]
- A directed acyclic graph identifies leaf nodes having zero dependents. [find_graph_leaves]
- A directed acyclic graph computes the longest weighted critical path and cumulative weight from node duration weights. [compute_critical_path]
- A wave scheduler resolves a next wave of ready nodes whose upstream dependencies have succeeded, ordered by priority descending. [resolve_next_execution_wave]
- A wave scheduler transitions a node to running state. [mark_node_running]
- A wave scheduler transitions a node to succeeded state and promotes unblocked dependents to ready. [mark_node_succeeded]
- A wave scheduler transitions a node to failed state and applies an assigned failure policy defaulting to fail fast. [mark_node_failed]
- When failure policy is fail fast, marking a node failed transitions all unstarted nodes to cancelled. [apply_fail_fast_policy]
- When failure policy is skip downstream, marking a node failed transitions all transitive dependents to skipped. [apply_skip_downstream_policy]
- When failure policy is continue on error, marking a node failed leaves unblocked independent nodes eligible for execution. [apply_continue_on_error_policy]
- A wave scheduler reports whether all registered graph nodes have reached terminal states, returning true when every node is terminal or the graph is empty. [check_execution_finished]
- A wave scheduler retrieves node states individually and across all nodes. [retrieve_node_states]
- A DAG runner executes graph waves concurrently under an assigned failure policy defaulting to fail fast and a maximum concurrency limit defaulting to four, applies retries, and returns a DAG run report. [run_graph_execution]
- When execution exceeds an allocated timeout, the DAG runner raises DAG timeout error. [handle_execution_timeout]
- When active execution is cancelled, the DAG runner transitions non-terminal nodes to cancelled and raises DAG cancelled error. [cancel_graph_execution]

### Woven Contracts

- Graph construction, validation, topological evaluation, and critical path analysis coordinate with wave scheduling, failure propagation, and concurrent execution. [add_node_to_graph, add_edge_between_nodes, validate_graph_invariants, compute_topological_sort, compute_critical_path, resolve_next_execution_wave, mark_node_succeeded, mark_node_failed, apply_fail_fast_policy, apply_skip_downstream_policy, apply_continue_on_error_policy, check_execution_finished, run_graph_execution, handle_execution_timeout, cancel_graph_execution]

## Grounding

### Knowledge Provisions

- Directed acyclic graph protocol, wave scheduler, DAG runner, lifecycle states, and run report. [dag_engine_core_service]

### Knowledge Requirements

- Graph data structures, topological sort algorithms, cycle detection traversal, and thread pool execution.
  - Deferred: Realized by concrete realization in dag_engine_impl.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-22T01:28:27Z
LAST_CHANGED: 2026-10-21T18:13:00Z
CHANGE: Align planning contracts with operation-driven failure policies and continue on error contract
SPEC_QA_AUDIT: 2026-10-22T01:28:27Z
-->
