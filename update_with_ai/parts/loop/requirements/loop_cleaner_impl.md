# loop_cleaner_impl implementation component

imports: loop_cleaner, loop_node_cleaner, dag_storage, dag_subgraph
implements: loop_cleaner

## Assumptions and Requirements

### Requirements

1. Target node scoping sets the target node on the dag subgraph to determine dependency-first topological order.
2. Cleaning processes ready batches of dirty nodes in topological order, recording node visits for each cleaned batch, and halts immediately if the node cleaner communicates that processing cannot continue.
3. Cleaning concludes when the dag subgraph is complete, indicating all reachable nodes in the target subgraph are clean.

## Grounding Facts

### Knowledge Needed

- Target root node.
- Ready batches from `dag_subgraph.DagSubgraph`.
- Node visit limits.
- Subgraph completion status from `dag_subgraph.DagSubgraph`.

### Actions Needed

- Set target root node on `dag_subgraph.DagSubgraph`.
- Dispatch ready batches to `loop_node_cleaner`.
- Record node visits in `dag_subgraph.DagSubgraph`.
- Halt on failure or conclude upon subgraph completion.
