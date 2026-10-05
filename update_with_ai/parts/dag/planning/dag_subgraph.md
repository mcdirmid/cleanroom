<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: a9e55d928ad1
-->

# dag_subgraph interface component

imports: dag_storage

## Intent

Multi-node agent workflows require coordinated traversal of dependency relationships, isolating active execution targets from unrelated workspace components. Querying unstructured graph storage directly forces execution runners to duplicate topological traversal algorithms, detect circular dependencies, and evaluate dirty node readiness independently. The dag_subgraph interface component establishes a focused query boundary over graph storage that models an active execution subgraph rooted at a target node.

By calculating dependency-first topological ordering, evaluating subgraph completion, batching ready dirty nodes by role address, and recording node visit limits, the component isolates graph query complexity from agent execution loops.

## Factored Contracts

### Contracts

- A caller supplies a target node in dag storage when setting a target node. [set_target_node_supplied]
- The dag subgraph collects reachable dependency nodes from the target node in dag storage. [collect_reachable_dependencies]
- The dag subgraph computes the dependency-first topological order of reachable dependency nodes. [compute_topological_order]
- The dag subgraph reports whether the target subgraph is complete. [report_subgraph_complete]
- The target subgraph is complete if, but only if, all reachable nodes in the target subgraph are clean in dag storage. [subgraph_complete_when_all_clean]
- The dag subgraph provides the next ready batch of dirty nodes to clean. [provide_next_ready_batch]
- Selected dirty nodes in the next ready batch are uncleaned. [ready_batch_nodes_uncleaned]
- Selected dirty nodes in the next ready batch are prioritized by role tier precedence. [ready_batch_prioritized_by_role_tier]
- Dependencies in the target subgraph for each selected dirty node in the next ready batch are clean in dag storage or present in the same ready batch. [ready_batch_dependencies_satisfied]
- Selected dirty nodes in the next ready batch share the same role address. [ready_batch_grouped_by_role]
- The next ready batch is bounded by a maximum batch size. [ready_batch_bounded_by_size]
- A caller supplies a batch of nodes when recording a visit. [record_visit_batch_supplied]
- The dag subgraph increments visit counts for each node in the recorded batch. [record_visit_increment_counts]
- The dag subgraph enforces execution iteration limits across recorded node visits. [record_visit_enforce_iteration_limits]

## Woven Contracts

- Setting a target node establishes an active execution subgraph containing reachable dependency nodes arranged in dependency-first topological order. \[set_target_node_supplied, collect_reachable_dependencies, compute_topological_order, dag_storage: [access_dag_dependencies]\]
- Evaluating completion status reports true if, but only if, every reachable node in the target subgraph is clean in dag storage. \[report_subgraph_complete, subgraph_complete_when_all_clean, dag_storage: [expose_node_dirty]\]
- Requesting the next ready batch yields uncleaned dirty nodes of the same role address prioritized by role tier precedence whose dependencies are clean or present in the same ready batch, up to the maximum batch size. \[provide_next_ready_batch, ready_batch_nodes_uncleaned, ready_batch_prioritized_by_role_tier, ready_batch_dependencies_satisfied, ready_batch_grouped_by_role, ready_batch_bounded_by_size, dag_storage: [expose_node_dirty]\]
- Recording a visit for a batch increments each node's visit count and enforces execution iteration limits. [record_visit_batch_supplied, record_visit_increment_counts, record_visit_enforce_iteration_limits]
