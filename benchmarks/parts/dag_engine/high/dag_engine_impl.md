# dag_engine_impl implementation component

implements: dag_engine

## Purpose

The dag_engine_impl implementation component realizes concrete Directed Acyclic Graph data structures, cycle detection algorithms, concurrent wave scheduling, and thread pool execution runners.

Reliable task graph execution requires robust synchronization across concurrent mutations, deterministic topological evaluation without arbitrary orderings, efficient critical path resolution, and resilient thread pool coordination. Without concrete data structures and thread-safe scheduling, concurrent execution risks race conditions, worker starvation, unobserved exceptions, and orphan threads. The dag_engine_impl implementation component provides synchronized adjacency graph storage, depth-first cycle verification, wave-based state machines, and bounded worker pools to execute task graphs safely.

**Out of scope:** The dag_engine_impl implementation component does not distribute tasks across network nodes or persist task checkpoints to disk; these are handled by other components.

## Types and Behavior

A *concrete directed acyclic graph* realizes the directed acyclic graph protocol using re-entrant locks for state synchronization. The graph indexes node definitions in an internal *node registry* and maintains bidirectional dependency relationships across an *adjacency index*. The adjacency index partitions connections into:

- Upstream prerequisite neighbor sets updated during node registration and edge addition.

- Downstream dependent neighbor sets updated during node registration and edge addition.

Node presence checks and removal operations update the node registry and clear incident connections across both adjacency sets under lock. Invariant validation detects cycles by executing depth-first traversal with active path recursion tracking, failing with cycle error upon discovering a back-edge.

Topological sorting evaluates graph structure using Kahn's algorithm, maintaining in-degree counts from the adjacency index and processing unblocked nodes in priority order. Critical path analysis resolves longest dependency bounds by applying dynamic programming over topological completion times, backtracking from the maximal completion leaf.

A *concrete wave scheduler* realizes the wave scheduler protocol by tracking execution states across an internal *state index* synchronized by re-entrant locks. The scheduler synchronizes state tracking dynamically with all registered nodes in the graph. State transitions evaluate:

- Initial state population assigning ready status to root nodes with empty upstream sets and pending status to remaining nodes.

- Wave extraction querying ready nodes whose upstream prerequisites in the adjacency index are all succeeded.

- Downstream promotion and failure policy propagation updating the state index in response to terminal node outcomes using the supplied failure policy.

- Completion verification confirming that every node in the graph is recorded in the state index and has reached a terminal state, returning true if all nodes are terminal or if the graph has no nodes, and false if any node remains non-terminal.

A *concrete DAG runner* realizes the DAG runner protocol by executing graph waves concurrently across a thread pool bounded by maximum concurrency. The runner enforces pre-execution invariant validation against the graph before commencing wave execution.

Execution advances by iteratively dispatching ready waves to worker threads, running task actions with retry backoff, propagating failure policies when marking node failures in the scheduler, and compiling terminal node outcomes into a consolidated DAG run report. Loop iterations sequentially evaluate cancellation events and timeout limits as independent loop guards before dispatching ready waves to worker threads.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-26T21:35:31Z
LAST_CHANGED: 2026-10-22T10:20:00Z
CHANGE: Realize concrete DAG, WaveScheduler, and DAGRunner as system singleton services with operation-driven failure propagation
SPEC_QA_AUDIT: 2026-10-26T21:35:31Z
-->
