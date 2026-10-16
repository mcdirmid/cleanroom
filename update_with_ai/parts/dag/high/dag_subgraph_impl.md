<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Remove interface-restated catalogs and retain only implementation-specific ordering and batching mechanics
CODE_HASH: 67d2e86d33fa
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dag_subgraph_impl implementation component

imports: dag_config, dag_storage
implements: dag_subgraph

## Purpose

The dag_subgraph_impl implementation component realizes active subgraph scoping, dependency-first topological ordering, ready node batching, and visit limit tracking.

Traversing multi-stage build workflows requires isolating reachable subgraphs, evaluating topological order deterministically, and tracking node visitation bounds to prevent infinite re-cleaning cycles. Hardcoding graph traversal algorithms into execution runners complicates scheduling logic and duplicates dependency validation. The dag_subgraph_impl implementation component provides an in-memory graph index over dag storage that orders reachable nodes deterministically and bounds cleaning iterations without re-reading graph structure on every query.

**Out of scope:** The dag_subgraph_impl implementation component does not execute node cleaning workloads, format file aliases, or manage persistent storage; these are handled by other components.

**Delegated:** Graph persistence and node state queries are delegated to dag_storage; batch size and node visit limits are delegated to dag_config.

## Types and Behavior

Setting a target node indexes every node reachable from the target node in dag storage, and orders those nodes in dependency-first topological order. Ordering emits a node only after its dependencies in the target subgraph, and breaks each remaining tie by role tier depth first, by unit address second, and by role address third.

The target subgraph is complete if, but only if, every indexed node is clean in dag storage.

The next ready batch draws from the indexed topological order, beginning at the earliest dirty node whose dependencies in the target subgraph are clean in dag storage, and extends over the contiguous nodes that share the first node's role address. A node whose dependencies in the target subgraph are neither clean nor already collected into the same batch leaves the batch before that node. The batch never exceeds the batch size of a system's dag config, and is an empty sequence when no dirty node in the target subgraph has all of its dependencies in the target subgraph clean in dag storage.

Recording a visit for a batch advances the visit count of each node in the batch, failing when any node exceeds the node visit limit of a system's dag config.
