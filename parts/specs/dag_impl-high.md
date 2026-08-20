# dag_impl

fulfills: dag
imports: dag_storage (graph + messages), dag_clean_logic (cleaning)
terms (from dag_storage): subgraph, dependency, reverse dependency, pending message, message
terms (from dag_clean_logic): dirty, cleaning, change message, feedback message

## Deltas beyond the dag contract

### Behavior

- Subgraph = target + transitive dependencies via dag_storage; topological sort computed once and fixed for the operation. Cycle in graph -> failure, state unchanged.
- Clean dirty nodes in topological order, only when all dependencies are clean; dirtiness re-evaluated after each cleaning; stop when no node in the sort is dirty.
- All reads and writes, including graph access, go through dag_storage without caching.
- Empty strings are valid messages.
- Messages are discrete items; multiple identical messages are allowed (no deduplication is performed).

### Ordering

- A cleaned node's change and feedback messages are routed before the node's data is deleted: routing reads the node's known reverse dependencies, which must still be present.
- Change messages are broadcast to the node's known reverse dependencies present in the graph; a known reverse dependency not in the graph (unresolvable) is skipped.

### Operation Boundaries

- Cleaning is atomic per node, per the dag contract. Subgraph cleaning as a whole is not atomic: successfully cleaned nodes retain their changes even if a later node fails.

### State Management

- No internal state; all state is delegated to dag_storage.

### Error Handling

- Cleaning failures, feedback targeting nodes outside the subgraph, and non-terminating cleaning are signaled per the interface contract.
- Concurrent cleaning operations, or a message arriving during cleaning, result in undefined behavior.
- Self-loops are treated as cycles: a graph containing a self-loop signals failure, leaving state unchanged.

## Non-concerns

- Ordering among nodes at the same topological level: any deterministic order is acceptable as long as dependencies are processed before dependents.
- Message ordering: the order of messages in a node's pending list is not semantically meaningful; FIFO, LIFO, or any other order is acceptable.
