# kahn_topology_ext external component

## Purpose

The kahn_topology_ext external component provides algorithmic reference knowledge for deterministic topological sorting via Kahn's algorithm with priority-ordered max-heap selection, cycle path reconstruction, and critical path dynamic programming.

Evaluating dependencies across directed acyclic graphs requires deterministic ordering of unblocked nodes, systematic cycle detection with informative path tracing, and longest-path critical path resolution. Without canonical queueing and tie-breaking algorithms, graph engines produce nondeterministic execution orders, fail to detect dependency cycles cleanly, or introduce fragile ad-hoc traversal routines. The kahn_topology_ext external component establishes these algorithmic reference mechanics independently of application services.

**Out of scope:** The kahn_topology_ext external component does not define task node lifecycles, wave scheduler state indices, failure policies, or execution runners; these are handled by other components.

## Grounding Gaps Covered

The kahn_topology_ext component provides algorithmic mechanics for deterministic Kahn's topological sorting, cycle detection, and critical path dynamic programming.

Grounding gaps covered include:

- In-degree tracking and queue initialization: Graph in-degrees are calculated across all registered nodes from upstream prerequisite mappings. Nodes possessing in-degree zero are enqueued into a max-heap keyed by descending priority and lexicographically ascending node identifier.

- Deterministic wave and topological extraction: The node with the highest priority (and lexicographically smallest identifier on priority ties) is popped from the heap and placed in the topological ordering. Downstream dependents' in-degrees decrement by one, and newly unblocked dependents (in-degree zero) push into the heap.

- Cycle detection and path reconstruction: When the number of ordered nodes is fewer than the total number of graph nodes, a directed cycle exists. The unplaced nodes are traversed using depth-first search to reconstruct the cyclic sequence of node identifiers forming the back-edge loop.

- Critical path dynamic programming: Earliest completion times are accumulated along topological ordering by summing node duration weights with maximal prerequisite completion times. The critical path sequence is reconstructed by backtracking from the leaf node exhibiting maximal cumulative duration.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-11-11T20:41:00Z
LAST_CHANGED: 2026-11-11T20:41:00Z
CHANGE: Grounding specification alignment for Kahn's topological sorting and critical path
SPEC_QA_AUDIT: 2026-11-11T20:41:00Z
-->
