# dag_cleaner_impl

imports: dag_storage, dag_node_cleaner, dag_cleaner
types from dag_storage: dag storage, node, pending message
types from dag_node_cleaner: node cleaner, change message, feedback message
types from dag_cleaner: dag cleaner
implements: dag cleaner

## Behavior

- A *dag cleaner* cleans dirty *nodes* in topological order, cleaning each *node* only when all of its dependencies are clean.
- A cleaned *node* with *change messages* broadcasts those messages to its recorded reverse dependencies in *dag storage*, then clears its data.
- A cleaned *node* with *feedback messages* routes them to the target dependencies and retains its data in *dag storage*.
- Cleaning is bounded by an execution limit to prevent infinite loops, concluding when all *nodes* in the acyclic subgraph are clean.
- When cleaning exceeds the execution limit, the *dag cleaner* halts with an unexpected failure.
