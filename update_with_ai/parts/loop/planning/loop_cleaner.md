# loop_cleaner interface component

imports: dag_storage, loop_node_cleaner

## Intent

Executing interconnected tasks in an arbitrary or concurrent sequence risks race conditions, duplicate computations, and stale artifact reads. When an upstream node changes, downstream dependents must be invalidated and updated in dependency order. The loop_cleaner interface component establishes an orchestration boundary that enforces topological execution across subgraphs.

By guaranteeing dependency-first evaluation order and halting promptly on unrecoverable node cleaner failures, the loop cleaner maintains graph consistency throughout execution passes.

## Factored Contracts

### Contracts

- A caller supplies a target node when cleaning a target node. [clean_target_supplied]
- A caller guarantees that the target node roots an acyclic subgraph. [caller_guarantees_target_roots_acyclic_subgraph]
- A caller supplies a node cleaner when cleaning a target node. [clean_node_cleaner_supplied]
- The loop cleaner cleans dirty nodes in dependency-first topological order. [clean_nodes_topological_order]
- The loop cleaner ensures all dependencies of a node are clean before that node is cleaned. [ensure_dependencies_clean_first]
- Cleaning dirty nodes halts if the node cleaner communicates that processing cannot continue. [halt_when_node_cleaner_cannot_continue]
- Cleaning concludes when all nodes in the subgraph rooted at the target node are clean. [conclude_when_all_nodes_clean]

### Woven Contracts

- The loop cleaner traverses dirty nodes in topological dependency order using the supplied node cleaner, halting if cleaning fails or concluding when all subgraph nodes are clean. [caller_guarantees_target_roots_acyclic_subgraph, clean_target_supplied, clean_node_cleaner_supplied, clean_nodes_topological_order, ensure_dependencies_clean_first, halt_when_node_cleaner_cannot_continue, conclude_when_all_nodes_clean, loop_node_cleaner: [clean_dirty_nodes, communicate_processing_continuation], dag_storage: [access_dag_dependencies, expose_node_dirty]]

## Grounding

### Knowledge Provisions

- Topological dependency-first cleaning traversal across target subgraphs. [loop_cleaner_service]

### Knowledge Requirements

- Subgraph topological traversal and batch dirty node discovery.
  - Deferred: Delegated to DagSubgraph in implementation.
- Delegation of ready batch workloads to NodeCleaner.
  - Deferred: Delegated to NodeCleaner in implementation.
