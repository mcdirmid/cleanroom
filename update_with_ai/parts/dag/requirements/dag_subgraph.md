# dag_subgraph interface component

imports: dag_storage

## Assumptions and Requirements

### Requirements

1. Setting a target collects all reachable dependency nodes from the target node in dag storage and computes their dependency-first topological order.
2. The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage.
3. When obtaining the next ready batch, uncleaned dirty nodes prioritized by role tier precedence (upstream roles before downstream roles) whose dependencies in the target subgraph are clean in dag storage or present in the same ready batch are selected, grouped by role address up to a maximum batch size.
4. Recording a visit increments the visit count for each node in the batch and raises an unexpected failure if visiting any node exceeds the node visit limit.

## Grounding Facts

### Knowledge Needed

- Target root node.
- Reachable dependency nodes and topological order.
- Node dirty status from `dag_storage`.
- Role tier precedence order.
- Batch size limit.
- Node visit counts and node visit limit.

### Actions Needed

- Collect reachable dependencies and compute topological sort.
- Check completeness across reachable nodes.
- Select next ready batch of dirty nodes grouped by role.
- Record node visits and enforce visit limits.
