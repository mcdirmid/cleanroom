# loop_cleaner interface component

imports: loop_node_cleaner, dag_storage

## Assumptions and Requirements

### Assumptions

1. It is assumed that the node roots an acyclic subgraph.

### Requirements

2. Cleaning a node cleans dirty nodes in dependency-first topological order, ensuring all dependencies of a node are clean before that node is cleaned.
3. Cleaning dirty nodes halts if the node cleaner communicates that processing cannot continue.
4. Cleaning concludes when all nodes in the subgraph rooted at the node are clean.

## Grounding Facts

### Knowledge Needed

- Root node of acyclic subgraph.
- Dependency-first topological order.
- Node dirty states.
- Cleaner continuation status.

### Actions Needed

- Clean dirty nodes in topological order via node cleaner.
- Halt cleaning if node cleaner signals processing cannot continue.
- Conclude when all subgraph nodes are clean.
