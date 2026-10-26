# dag_engine_lite_impl implementation component

implements: dag_engine_lite

## Purpose

The dag_engine_lite_impl implementation component realizes concrete Directed Acyclic Graph data structures, cycle detection algorithms, sequential wave scheduling, and deterministic execution runners.

Reliable task graph execution requires deterministic topological evaluation without arbitrary orderings, efficient critical path resolution, and resilient sequential wave coordination. Without concrete data structures and disciplined state scheduling, execution risks cyclic hangs, unhandled task errors, and incorrect transitive state invalidation. The dag_engine_lite_impl implementation component provides adjacency graph storage, depth-first cycle verification, wave-based state machines, and sequential runners to execute task graphs safely and deterministically.

**Out of scope:** The dag_engine_lite_impl implementation component does not distribute tasks across network nodes or persist task checkpoints to disk; these are handled by other components.

## Types and Behavior

A *concrete directed acyclic graph* realizes the directed acyclic graph protocol by indexing node definitions in an internal *node registry* and maintaining bidirectional dependency relationships across an *adjacency index*. The adjacency index partitions connections into:

- Upstream prerequisite neighbor sets updated during node registration and edge addition.

- Downstream dependent neighbor sets updated during node registration and edge addition.

Node presence checks and removal operations update the node registry, clear incident connections across both adjacency sets, and purge removed node records from active wave scheduler tracking. Invariant validation detects cycles by executing depth-first traversal with active path recursion tracking, failing with cycle error upon discovering a back-edge.

Topological sorting evaluates graph structure using Kahn's algorithm, maintaining in-degree counts from the adjacency index and processing unblocked nodes in priority order, resolving ties between equal-priority nodes by lexicographically ascending node identifier. Critical path analysis resolves longest dependency bounds by applying dynamic programming over topological completion times, backtracking from the maximal completion leaf.

A *concrete wave scheduler* realizes the wave scheduler protocol by tracking execution states across an internal *state index*. The scheduler synchronizes state tracking dynamically with all registered nodes in the graph, purging states for nodes removed from the graph. State transitions evaluate:

- Initial state population assigning ready status to root nodes with empty upstream sets and pending status to remaining nodes.

- Unblocked dependent promotion advancing downstream nodes to ready when all upstream dependencies succeed.

- Downstream promotion and failure policy propagation updating the state index in response to terminal node outcomes using the supplied failure policy, transitioning unreachable dependents of failed nodes to skipped under continue on error.

- Completion verification confirming that every registered node in the graph is recorded in the state index and has reached a terminal state (or that no executable nodes remain and any uncompleted nodes cannot run due to failed dependencies), returning true if all nodes are terminal or if the graph has no nodes, and false if any node remains non-terminal and eligible.

A *concrete DAG runner* realizes the DAG runner protocol by executing graph waves sequentially to completion. The runner enforces pre-execution invariant validation against the graph before commencing wave execution.

Execution advances by iteratively polling the wave scheduler, running unblocked node actions with retry attempts, propagating failure policies when marking node failures in the scheduler, and compiling terminal node outcomes into a consolidated DAG run report with succeeded, failed, skipped, and cancelled node sequences.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T20:55:00Z
LAST_CHANGED: 2026-10-26T20:55:00Z
CHANGE: Specify scheduler state purge on node removal, tie-breaking lexicographical ordering, and terminal state transitions under continue on error
SPEC_QA_AUDIT: 2026-10-26T20:55:00Z
-->
