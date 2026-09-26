# dag_subgraph_impl implementation component

imports: dag_config, dag_storage
implements: dag_subgraph

## Assumptions and Requirements

### Requirements

1. Setting a target node scopes the target subgraph to all reachable dependency nodes rooted at the target node in dag storage, arranged in dependency-first topological order, breaking ties by role tier depth first, then by unit address.
2. The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage.
3. The next ready batch consists of contiguous dirty nodes in topological order that share the same role address, prioritized by role tier precedence (prioritizing lib before test, and test before qa) and having all their dependencies in the target subgraph clean in dag storage or present in the same ready batch, starting from the earliest ready dirty node in topological order and bounded by the batch size obtained from dag config.
4. If no dirty node in the target subgraph has all its dependencies in the target subgraph clean in dag storage, the next ready batch is an empty sequence.
5. Recording a visit for a batch of nodes advances the visit count for each node in the batch, raising an unexpected failure if any node exceeds the node visit limit obtained from dag config.

## Grounding Facts

### Knowledge Needed

- Target root node.
- Reachable dependency nodes and topological order.
- Node dirty states from `dag_storage`.
- Role tier precedence order.
- Batch size limit from `dag_config`.
- Node visit counts and limit from `dag_config`.

### Actions Needed

- Scope target subgraph and order reachable dependency nodes.
- Verify subgraph cleanliness against `dag_storage`.
- Filter and group ready dirty nodes by role address up to batch size.
- Increment visit counts and enforce visit ceiling.
