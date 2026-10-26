# dag_engine_lite interface component

## Intent

Dependency-driven task pipelines require declarative, cycle-safe graph structures to represent prerequisite relationships, schedule sequential execution waves, manage retries, and isolate failures without concurrency overhead. The dag_engine_lite interface component defines abstract protocols and data types for constructing Directed Acyclic Graphs, partitioning ready nodes into sequential waves, tracking execution states, and computing critical path metrics.

By factoring graph construction, topological sorting, failure propagation policies, and execution orchestration into decoupled protocols, the component enables deterministic execution and thorough verification of task pipelines while keeping worker thread pools, system locks, and operating system subprocesses outside its boundary.

## Factored Contracts

### Typing

- A DAG error carries a diagnostic error message.
- A cycle error carries an error message and a cycle sequence of node identifiers.
- A node not found error carries an error message and a missing node identifier.
- A node execution error carries an error message, a failed node identifier, and an underlying caught cause.
- A node state takes the form of pending, ready, running, succeeded, failed, cancelled, or skipped.
- A failure policy takes the form of fail fast, continue on error, or skip downstream.
- A node definition carries a node identifier, a zero-argument callable action, a set of upstream dependency identifiers, a scheduling priority, and a permitted retry count.
- A node result carries a node identifier, a terminal node state, an optional returned value, an optional caught error, an elapsed duration, and an attempted retry count.
- A DAG run report carries a total node count, succeeded node identifiers, failed node identifiers, skipped node identifiers, cancelled node identifiers, a wall clock duration, a critical path sequence of node identifiers, and a results mapping from node identifiers to node results.
- A directed acyclic graph maintains task nodes and directed dependency edges between prerequisites and dependents.
- A wave scheduler partitions and coordinates graph nodes into sequential execution waves.
- A DAG runner coordinates sequential graph execution under a configured failure policy.

### Contracts

- A directed acyclic graph adds a task node with a callable action, dependency identifiers, a scheduling priority, and a retry count, deferring missing dependency validation to graph validation. [add_node_to_graph]
- A directed acyclic graph adds a directed dependency edge from an upstream prerequisite to a downstream dependent. [add_edge_between_nodes]
- When an edge addition or a node removal references a node absent from the graph, the graph raises node not found error. [raise_node_not_found_on_missing_reference]
- A directed acyclic graph removes a node together with its incident edges, purging removed nodes from wave scheduler tracking. [remove_node_from_graph]
- A directed acyclic graph tests whether a node identifier is present. [test_node_presence]
- A directed acyclic graph retrieves the immutable definition of a registered node. [retrieve_node_definition]
- A directed acyclic graph retrieves the direct upstream dependencies of a node. [retrieve_upstream_dependencies]
- A directed acyclic graph retrieves the direct downstream dependents of a node. [retrieve_downstream_dependents]
- A directed acyclic graph lists all registered node identifiers. [list_all_graph_nodes]
- A directed acyclic graph validates graph invariants for referenced dependency existence and directed acyclicity. [validate_graph_invariants]
- When a referenced dependency identifier corresponds to no registered node, invariant validation raises node not found error. [raise_node_not_found_on_dangling_dependency]
- When invariant validation detects a directed cycle, the graph raises cycle error carrying the cycle sequence. [raise_cycle_error_on_directed_cycle]
- A directed acyclic graph computes a topological sort ordering prerequisites before dependents. [compute_topological_sort]
- A directed acyclic graph breaks topological ties between ready nodes by descending scheduling priority then lexicographically ascending node identifier. [break_topological_ties_deterministically]
- When a cycle prevents topological ordering, the graph raises cycle error carrying the cycle sequence. [raise_cycle_error_on_topological_sort]
- A directed acyclic graph identifies root nodes having zero dependencies. [find_graph_roots]
- A directed acyclic graph identifies leaf nodes having zero dependents. [find_graph_leaves]
- A directed acyclic graph computes the critical path as the longest weighted path through the graph together with its cumulative duration weight. [compute_critical_path]
- When no duration weight is supplied for a node, critical path computation assigns a duration weight of one. [default_critical_path_weights_to_one]
- A wave scheduler resolves a next wave of ready nodes whose upstream dependencies have succeeded. [resolve_next_execution_wave]
- A wave scheduler orders a resolved wave by descending scheduling priority then ascending node identifier. [order_wave_by_priority_then_identifier]
- When no node is ready, the wave scheduler resolves an empty wave sequence. [resolve_empty_wave_when_no_nodes_ready]
- A wave scheduler transitions a node to running state. [mark_node_running]
- A wave scheduler transitions a node to succeeded state. [mark_node_succeeded]
- A wave scheduler promotes unblocked dependents to ready state when all of their upstream dependencies have succeeded. [promote_unblocked_dependents]
- A wave scheduler transitions a node to failed state and applies an assigned failure policy defaulting to fail fast. [mark_node_failed]
- When the failure policy is fail fast, marking a node failed transitions all remaining pending nodes to cancelled. [apply_fail_fast_policy]
- When the failure policy is skip downstream, marking a node failed transitions all transitive dependents to skipped. [apply_skip_downstream_policy]
- When the failure policy is continue on error, marking a node failed leaves unblocked independent nodes eligible for execution while transitioning blocked dependents that cannot execute due to upstream failure to skipped. [apply_continue_on_error_policy]
- A wave scheduler reports whether execution is finished, returning true when every registered node is in a terminal state (or when no ready nodes remain and unexecuted nodes are blocked by upstream failures) or the graph is empty. [check_execution_finished]
- A wave scheduler retrieves node states individually and across all nodes, reflecting only currently registered nodes. [retrieve_node_states]
- A DAG runner runs a graph to completion by dispatching ready waves sequentially under an assigned failure policy defaulting to fail fast. [run_graph_execution]
- A DAG runner validates graph invariants prior to commencing wave execution. [validate_invariants_before_execution]
- A DAG runner executes a node action and retries it up to the configured retry count upon action failure. [execute_node_action_with_retries]
- When a node action raises an unhandled exception, the DAG runner records node execution error carrying the failed node identifier and the underlying cause. [capture_node_execution_error]
- A DAG runner compiles execution results into a DAG run report. [compile_run_report]

### Woven Contracts

- Graph construction, validation, topological evaluation, and critical path analysis coordinate with wave scheduling, failure propagation, and sequential execution. [add_node_to_graph, add_edge_between_nodes, validate_graph_invariants, compute_topological_sort, compute_critical_path, resolve_next_execution_wave, mark_node_succeeded, mark_node_failed, check_execution_finished, run_graph_execution]
- Failure policy propagation and retry handling compose so that wave scheduling determines which nodes are cancelled, skipped, or left eligible while the DAG runner reports those terminal outcomes in a DAG run report. [apply_fail_fast_policy, apply_skip_downstream_policy, apply_continue_on_error_policy, execute_node_action_with_retries, capture_node_execution_error, compile_run_report]

## Grounding

### Knowledge Provisions

- Directed acyclic graph protocol, wave scheduler, DAG runner, node lifecycle states, failure policy outcomes, and DAG run report metrics. [dag_engine_lite_core_service]

### Knowledge Requirements

- Graph data structures, topological sort algorithms, cycle detection traversal, and sequential wave execution.
  - Deferred: Realized by concrete realization in dag_engine_lite_impl.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T20:55:00Z
LAST_CHANGED: 2026-10-26T20:55:00Z
CHANGE: Specify deferred missing dependency validation, ascending alphabetical tie-breaking, and SKIP state for blocked dependents
SPEC_QA_AUDIT: 2026-10-26T20:55:00Z
-->
