# Concrete scenarios for dag_engine_lite interface

## Scenario 1 — Linear graph construction and topological sort

Given: A newly initialized directed acyclic graph containing zero nodes.

1. Add node `task_a` with zero dependencies and scheduling priority 10.
Observed: Node `task_a` is present in the graph with 0 dependencies.

2. Add node `task_b` depending on `task_a` with scheduling priority 5.
Observed: Node `task_b` is present and depends directly on `task_a`.

3. Execute topological sort on the graph.
Observed: The returned sequence is `task_a` followed by `task_b`.

## Scenario 2 — Cycle detection during graph validation

Given: A directed acyclic graph containing nodes `step_1` and `step_2` where `step_2` depends on `step_1`.

1. Add a directed dependency edge from `step_1` to `step_2`.
Observed: The edge is added, so `step_1` depends on `step_2` while `step_2` still depends on `step_1`.

2. Validate graph invariants.
Observed: A cycle error is raised carrying the cycle sequence `step_1`, `step_2`, `step_1`.

## Scenario 3 — Referencing missing dependency raises error

Given: A directed acyclic graph containing registered node `node_x`.

1. Add a directed edge from missing node `node_missing` to `node_x`.
Observed: A node not found error is raised identifying missing node `node_missing`.

## Scenario 4 — Wave scheduler resolves ready nodes with priority tie-breaking

Given: A wave scheduler managing a graph with independent root nodes `task_low` with priority 5, `task_high` with priority 10, and `task_mid` with priority 5.

1. Request the next execution wave from the scheduler.
Observed: The returned wave sequence is `task_high`, `task_low`, `task_mid`.

2. Mark node `task_high` running.
Observed: Node `task_high` transitions to state running.

## Scenario 5 — Failure policy propagates skip downstream to dependents

Given: A wave scheduler managing node `parent_node` and dependent node `child_node`.

1. Mark `parent_node` as failed with failure policy skip downstream.
Observed: Node `parent_node` transitions to state failed, and dependent node `child_node` transitions to state skipped.

## Scenario 6 — Critical path calculation with weighted node durations

Given: A directed acyclic graph with root `node_start` having duration 2.5, intermediate node `node_branch` having duration 4.0 depending on `node_start`, and leaf `node_end` having duration 1.5 depending on `node_branch`.

1. Compute critical path across the graph.
Observed: The critical path sequence is `node_start`, `node_branch`, `node_end` with cumulative weight 8.0.

## Scenario 7 — Sequential runner execution and run report compilation

Given: A DAG runner managing a graph with independent root node `worker_1` and dependent node `worker_2`.

1. Execute the DAG runner run operation with failure policy continue on error.
Observed: The returned DAG run report records total node count 2, succeeded node identifiers `worker_1` and `worker_2`, and 0 failed node identifiers.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-22T10:20:00Z
LAST_CHANGED: 2026-10-22T10:20:00Z
CHANGE: Specify failure policy on mark_failed and run steps
SPEC_QA_AUDIT: 2026-10-22T10:20:00Z
-->
