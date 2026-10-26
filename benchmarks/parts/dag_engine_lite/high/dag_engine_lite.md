# dag_engine_lite interface component

## Purpose

The dag_engine_lite interface component defines abstract graph structures, validation contracts, deterministic wave scheduling, failure propagation policies, and execution reporting for Directed Acyclic Graphs.

Orchestrating task pipelines requires formal representation of task dependencies, deterministic topological evaluation, invariant cycle validation, and structured failure handling. Without uniform graph contracts, execution engines suffer from cyclic dependency loops, unhandled cascading failures, inconsistent tie-breaking, and untracked critical paths. The dag_engine_lite interface component provides canonical data representations and protocols for dependency graphs, wave schedulers, and execution runners to ensure safe, reproducible task graph execution without concurrency overhead.

**Out of scope:** The dag_engine_lite interface component does not allocate worker thread pools, manage system locks, or execute operating system subprocesses; these are handled by other components.

## Types and Behavior

A *DAG error* serves as the base error for graph operations, carrying a diagnostic *error message*. Graph operation failures are categorized into:

- A *cycle error* indicating a directed dependency cycle within a graph, carrying a *cycle sequence* of node identifiers.

- A *node not found error* indicating a referenced node is absent from a graph, carrying a missing *node identifier*.

- A *node execution error* indicating an unhandled exception occurred during task execution, carrying a failed node identifier and a caught *underlying cause*.

A *node state* represents the lifecycle condition of a graph node, taking the form of *pending*, *ready*, *running*, *succeeded*, *failed*, *cancelled*, or *skipped*. A *failure policy* defines how execution responds to a failed node, taking the form of *fail fast*, *continue on error*, or *skip downstream*.

A *node definition* represents an immutable task node within a graph, carrying a node identifier, a zero-argument *callable action*, a set of upstream *dependency identifiers*, a numeric *scheduling priority*, and a *permitted retry count*.

A *node result* records the execution outcome of a task node, carrying a node identifier, a terminal node state, an optional *returned value*, an optional *caught error*, an *elapsed duration*, and an *attempted retry count*.

A *DAG run report* summarizes an entire graph execution run, carrying a *total node count*, *succeeded node identifiers*, *failed node identifiers*, *skipped node identifiers*, *cancelled node identifiers*, a *wall clock duration*, a *critical path sequence* of node identifiers, and an execution *results mapping* from node identifiers to node results.

A *directed acyclic graph* maintains task nodes and directed dependency edges between prerequisites and dependents. Graph modification operations provide:

- Adding nodes with callable actions, dependency identifiers, scheduling priorities, and retry counts, deferring missing dependency validation to graph validation and topological sort rather than eagerly failing upon node registration.

- Adding edges from upstream prerequisites to downstream dependents, raising node not found error when either node is missing.

- Removing nodes and incident edges, raising node not found error when the node is missing, purging removed nodes from wave scheduler state tracking.

Graph inspection supports testing node presence, retrieving node definitions, retrieving dependencies, retrieving dependents, and listing all nodes. Graph invariant validation verifies that all referenced dependencies exist and raises cycle error upon detecting directed cycles.

Graph ordering and structural analysis provide:

- Computing a topological sort where prerequisites precede dependents, deterministically breaking ties between ready nodes by descending scheduling priority then lexicographically ascending node identifier, raising cycle error if cycles exist.

- Finding root nodes with zero dependencies and finding leaf nodes with zero dependents.

- Computing critical paths, resolving the longest weighted path through the graph and its cumulative duration weight using optional duration weights defaulting to one.

A *wave scheduler* partitions and coordinates graph nodes into executable sequential waves. The scheduler dynamically tracks execution states for all registered nodes in the graph, reflecting only nodes currently registered in the graph and resolving a *next wave* of ready nodes whose upstream dependencies have succeeded, ordered by descending scheduling priority then ascending node identifier, returning an empty sequence when no nodes are ready.

The scheduler supports marking nodes running, marking nodes succeeded and promoting unblocked dependents to ready, and marking nodes failed under an assigned failure policy defaulting to fail fast. When marking a node failed, failure policy propagation enforces:

- Transitioning all remaining pending nodes to cancelled under the fail fast policy.

- Transitioning all transitive dependents to skipped under the skip downstream policy.

- Leaving unblocked independent nodes eligible for execution under the continue on error policy, while transitioning blocked dependents that cannot execute due to upstream failure to skipped.

The scheduler tests whether execution is finished when all registered nodes in the graph have reached terminal states (succeeded, failed, cancelled, or skipped), or when no unblocked nodes remain and any remaining nodes cannot execute due to prerequisite failures, or when the graph contains no nodes, and supports retrieving node states individually and across all nodes.

A *DAG runner* coordinates sequential graph execution under failure policies. The runner supports running graphs to completion under an assigned failure policy defaulting to fail fast, validating graph invariants prior to execution, dispatching ready waves sequentially, executing configured retries upon action failures, and compiling execution results into a DAG run report.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T20:55:00Z
LAST_CHANGED: 2026-10-26T20:55:00Z
CHANGE: Clarify deferred dependency validation on add_node, scheduler purge on remove_node, tie-breaking lexicographical ordering, and terminal state transitions under continue on error
SPEC_QA_AUDIT: 2026-10-26T20:55:00Z
-->
