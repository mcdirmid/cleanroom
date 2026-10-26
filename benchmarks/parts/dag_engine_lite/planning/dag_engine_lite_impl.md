# dag_engine_lite_impl implementation component

## Intent

Concrete realization of the lightweight DAG execution engine requires straightforward adjacency data structures, cycle detection via depth-first traversal, deterministic priority-driven topological ordering, wave-based state promotion, and sequential task action execution. The dag_engine_lite_impl implementation component implements these capabilities as concrete classes realizing the dag_engine_lite interface.

By encapsulating adjacency index management, employing Kahn's algorithm for deterministic topological scheduling, and using sequential loops to manage wave execution and retries without concurrency overhead, the component provides robust and fully deterministic task graph execution.

## Factored Contracts

### Typing

- A concrete directed acyclic graph maintains an internal node registry and an adjacency index.
- A concrete wave scheduler maintains a graph reference and an internal state index.
- A concrete DAG runner manages a wave scheduler, sequential wave iteration, and a results mapping.

### Contracts

- A concrete directed acyclic graph indexes node definitions in an internal node registry. [maintain_node_registry]
- A concrete directed acyclic graph maintains an adjacency index partitioning upstream prerequisite neighbor sets and downstream dependent neighbor sets. [maintain_adjacency_maps]
- A concrete directed acyclic graph updates upstream and downstream neighbor sets during node registration and edge addition. [update_neighbor_sets_on_registration]
- A concrete directed acyclic graph tests node presence directly against the node registry. [test_node_registry_membership]
- A concrete directed acyclic graph removes node registry entries, clears incident connections across both adjacency sets upon node removal, and purges removed nodes from wave scheduler tracking. [purge_incident_connections_on_removal]
- A concrete directed acyclic graph rejects unregistered dependencies with node not found error upon lookup or edge insertion, deferring missing dependency validation on node addition. [enforce_node_presence]
- A concrete directed acyclic graph detects cycles by executing depth-first traversal with active path recursion tracking. [detect_graph_cycles]
- When depth-first traversal discovers a back-edge, the concrete directed acyclic graph raises cycle error. [raise_cycle_error_on_back_edge]
- A concrete directed acyclic graph computes topological sort using Kahn's algorithm with in-degree counts maintained from the adjacency index. [execute_deterministic_topological_sort]
- A concrete directed acyclic graph processes unblocked nodes in descending priority then lexicographically ascending node identifier order during topological sorting. [order_unblocked_nodes_by_priority]
- A concrete directed acyclic graph computes critical path bounds by applying dynamic programming over topological completion times. [compute_critical_path_dp]
- A concrete directed acyclic graph backtracks from the maximal completion leaf to resolve the critical path. [backtrack_from_maximal_completion_leaf]
- A concrete wave scheduler populates initial states by assigning ready status to root nodes with empty upstream sets and pending status to remaining nodes. [initialize_scheduler_states]
- A concrete wave scheduler extracts ready nodes whose upstream prerequisites in the adjacency index are all succeeded. [filter_and_order_ready_wave]
- A concrete wave scheduler orders an extracted wave by descending priority then ascending node identifier. [order_extracted_wave_by_priority]
- A concrete wave scheduler promotes pending dependents to ready when all upstream prerequisites transition to succeeded. [promote_unblocked_dependents]
- A concrete wave scheduler applies fail fast by cancelling all remaining pending nodes upon a node failure. [apply_fail_fast_cancellation]
- A concrete wave scheduler applies skip downstream by marking all transitive dependents skipped upon a node failure. [apply_skip_downstream_marking]
- A concrete wave scheduler applies continue on error by leaving unblocked independent nodes eligible for execution while transitioning blocked dependents that cannot execute due to upstream failure to skipped. [apply_continue_on_error_eligibility]
- A concrete wave scheduler confirms that every registered node in the graph is recorded in the state index and has reached a terminal state (or that no ready nodes remain and unexecuted nodes are blocked by upstream failures), returning true if all nodes are terminal or if the graph has no nodes, and false if any node remains non-terminal and eligible. [verify_scheduler_completion]
- A concrete DAG runner validates graph invariants before commencing wave execution. [pre_validate_graph_before_run]
- A concrete DAG runner polls the wave scheduler and dispatches ready waves sequentially until execution completes. [dispatch_sequential_waves]
- A concrete DAG runner executes node actions with retry attempts, compiling succeeded node results or failed node execution errors. [execute_node_action_with_retries]
- A concrete DAG runner marks node failures in the wave scheduler with the supplied failure policy upon unrecoverable action failure. [propagate_runner_failure_policy]
- A concrete DAG runner compiles terminal node outcomes and critical path metrics into a consolidated DAG run report. [compile_dag_run_report]

### Woven Contracts

- Node registry indexing, adjacency maintenance, depth-first cycle detection, Kahn topological sorting, wave state transitions, and sequential runners coordinate to execute task graphs safely and deterministically. [maintain_node_registry, maintain_adjacency_maps, enforce_node_presence, detect_graph_cycles, execute_deterministic_topological_sort, compute_critical_path_dp, initialize_scheduler_states, filter_and_order_ready_wave, promote_unblocked_dependents, apply_fail_fast_cancellation, apply_skip_downstream_marking, verify_scheduler_completion, pre_validate_graph_before_run, dispatch_sequential_waves, execute_node_action_with_retries, propagate_runner_failure_policy, compile_dag_run_report]
- Pre-execution invariant validation, wave extraction ordering, and retry-bearing action execution compose so that failure policy propagation determines which terminal outcomes the run report consolidates. [pre_validate_graph_before_run, filter_and_order_ready_wave, execute_node_action_with_retries, propagate_runner_failure_policy, apply_fail_fast_cancellation, apply_skip_downstream_marking, apply_continue_on_error_eligibility, compile_dag_run_report]

## Grounding

### Knowledge Provisions

- Concrete directed acyclic graph realization, wave scheduler state machine, and sequential execution runner in the system lifecycle tier. [concrete_dag_engine_lite_realization]

### Inherited Deferred Requirements

- Graph data structures, topological sort algorithms, cycle detection traversal, and sequential wave execution.
  - Grounded: [concrete_dag_engine_lite_realization]

### Knowledge Requirements

- Directed acyclic graph protocol, wave scheduler, DAG runner, node lifecycle states, failure policy outcomes, and DAG run report metrics.
  - Grounded: [dag_engine_lite: [dag_engine_lite_core_service]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T20:55:00Z
LAST_CHANGED: 2026-10-26T20:55:00Z
CHANGE: Specify dynamic scheduler state synchronization on remove_node, ascending alphabetical tie-breaking, and SKIP state for blocked dependents
SPEC_QA_AUDIT: 2026-10-26T20:55:00Z
-->
