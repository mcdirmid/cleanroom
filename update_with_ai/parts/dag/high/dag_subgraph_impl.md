# dag_subgraph_impl implementation component

imports: dag_config, dag_storage
implements: dag_subgraph

## Purpose

The dag_subgraph_impl implementation component realizes active subgraph scoping, dependency-first topological ordering, ready node batching, and visit limit tracking.

Traversing multi-stage build workflows requires isolating reachable subgraphs, evaluating topological order deterministically, and tracking node visitation bounds to prevent infinite re-cleaning cycles. Hardcoding graph traversal algorithms into execution runners complicates scheduling logic and duplicates dependency validation. The dag_subgraph_impl implementation component provides an in-memory graph index over dag storage that maintains topological ordering, groups ready dirty nodes by role address up to configured batch limits, and enforces visit limits across cleaning iterations.

**Out of scope:** The dag_subgraph_impl implementation component does not execute node cleaning workloads, format file aliases, or manage persistent storage; these are handled by other components.

## Types and Behavior

The dag subgraph service coordinates topological subgraph queries and visit bounds across dag storage.

Setting a target node scopes the target subgraph to all reachable dependency nodes rooted at the target node in dag storage, arranged in dependency-first topological order, breaking ties by role tier depth first, then by unit address.

The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage.

The next ready batch consists of contiguous dirty nodes in topological order that share the same role address, prioritized by role tier precedence (prioritizing lib before test, and test before qa) and having all their dependencies in the target subgraph clean in dag storage or present in the same ready batch, starting from the earliest ready dirty node in topological order and bounded by the batch size obtained from dag config. If no dirty node in the target subgraph has all its dependencies in the target subgraph clean in dag storage, the next ready batch is an empty sequence.

Recording a visit for a batch of nodes advances the visit count for each node in the batch, raising an unexpected failure if any node exceeds the node visit limit obtained from dag config.
