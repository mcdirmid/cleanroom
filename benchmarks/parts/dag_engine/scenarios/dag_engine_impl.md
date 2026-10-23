# Concrete scenarios for dag_engine_impl implementation

## Reused from the interface

### Scenario 1 — Linear graph construction and topological sort

Given: A newly initialized directed acyclic graph containing zero nodes.

1. Add node `task_a` with zero dependencies and scheduling priority 10.
Observed: Node `task_a` is present in the graph with 0 dependencies.
Realized by: Synchronizing under re-entrant lock, registering `task_a` in the internal node registry, and initializing empty adjacency sets.

2. Add node `task_b` depending on `task_a` with scheduling priority 5.
Observed: Node `task_b` is present and depends directly on `task_a`.
Realized by: Registering `task_b` in the node registry and adding an edge from `task_a` in the downstream map and `task_b` in the upstream map.

3. Execute topological sort on the graph.
Observed: The returned sequence is `task_a` followed by `task_b`.
Realized by: Computing in-degrees from the upstream map, enqueueing zero in-degree root `task_a`, and traversing downstream to `task_b`.

### Scenario 2 — Cycle detection during graph validation

Given: A directed acyclic graph containing nodes `step_1` and `step_2` where `step_2` depends on `step_1`.

1. Add a directed dependency edge from `step_2` to `step_1`.
Observed: The edge is added, creating a mutual dependency.
Realized by: Updating upstream and downstream maps under re-entrant lock without intermediate validation.

2. Validate graph invariants.
Observed: A cycle error is raised carrying the cycle sequence `step_1`, `step_2`, `step_1`.
Realized by: Running depth-first traversal with active path recursion tracking and detecting the back-edge to `step_1`.

### Scenario 3 — Referencing missing dependency raises error

Given: A directed acyclic graph containing registered node `node_x`.

1. Add a directed edge from missing node `node_missing` to `node_x`.
Observed: A node not found error is raised identifying missing node `node_missing`.
Realized by: Verifying node existence in the internal node registry and raising node not found error prior to mutating adjacency maps.

### Scenario 4 — Wave scheduler resolves ready nodes with priority tie-breaking

Given: A wave scheduler managing a graph with independent root nodes `task_low` with priority 1, `task_high` with priority 10, and `task_mid` with priority 5.

1. Request the next execution wave from the scheduler.
Observed: The returned wave sequence is `task_high`, `task_mid`, `task_low`.
Realized by: Filtering ready nodes with empty or satisfied dependencies and sorting by priority descending.

2. Mark node `task_high` running.
Observed: Node `task_high` transitions to state running.
Realized by: Updating the internal state tracking map entry for `task_high` to running under lock.

### Scenario 5 — Failure policy propagates skip downstream to dependents

Given: A wave scheduler managing node `parent_node` and dependent node `child_node`.

1. Mark `parent_node` as failed with failure policy skip downstream.
Observed: Node `parent_node` transitions to state failed, and dependent node `child_node` transitions to state skipped.
Realized by: Setting `parent_node` to failed, querying downstream dependents from the DAG, and marking transitive dependents skipped under the supplied failure policy.

### Scenario 6 — Critical path calculation with weighted node durations

Given: A directed acyclic graph with root `node_start` having duration 2.5, intermediate node `node_branch` having duration 4.0 depending on `node_start`, and leaf `node_end` having duration 1.5 depending on `node_branch`.

1. Compute critical path across the graph.
Observed: The critical path sequence is `node_start`, `node_branch`, `node_end` with cumulative weight 8.0.
Realized by: Performing topological ordering, applying dynamic programming over duration weights, and backtracking from the maximum completion leaf.

## Implementation-only

### Scenario 7 — Concurrent runner execution across thread pool

Given: A DAG runner managing independent nodes `worker_1` and `worker_2`.

1. Execute the DAG runner run operation with maximum concurrency 2 and fail fast policy.
Observed: Both `worker_1` and `worker_2` complete with state succeeded in the returned DAG run report.
Realized by: Submitting ready wave nodes to a thread pool executor bounded by maximum concurrency, awaiting completion, and aggregating individual node results into a run report.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-21T18:13:00Z
LAST_CHANGED: 2026-10-21T18:13:00Z
CHANGE: Align scenarios with operation-driven failure policies and concurrency limits
SPEC_QA_AUDIT: 2026-10-19T23:50:00Z
-->
