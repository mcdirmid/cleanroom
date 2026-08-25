# dag_cleaner_impl

fulfills: dag_cleaner
imports: dag_storage (graph + messages), dag_clean_logic (cleaning)
terms (from dag_storage): subgraph, dependency, reverse dependency, pending message, message
terms (from dag_clean_logic): dirty, cleaning, change message, feedback message

## Deltas

- All reads and writes, including graph access, go through dag_storage without caching.
- Empty strings are valid messages.
- Messages are discrete items; multiple identical messages are allowed (no deduplication is performed).
- [ordering] A cleaned node's change messages are routed before the node's data is deleted: routing reads the node's known reverse dependencies, which must still be present.
- A change result is applied by deleting the node's data after routing; a no-change result by clearing the node's pending messages; a feedback result by leaving the node's data untouched.
- [ordering] Change messages are broadcast to the node's known reverse dependencies present in the graph; a known reverse dependency not in the graph (unresolvable) is skipped.
- [boundary] Subgraph cleaning as a whole is not atomic: successfully cleaned nodes retain their changes even if a later node fails.
- [state] No internal state; all state is delegated to dag_storage.
- [failure] Concurrent cleaning operations, or a message arriving during cleaning, result in undefined behavior.
- [failure] Self-loops are treated as cycles: a graph containing a self-loop signals failure, leaving state unchanged.

## Non-concerns

- Ordering among nodes at the same topological level: any deterministic order is acceptable as long as dependencies are processed before dependents.
- Message ordering: the order of messages in a node's pending list is not semantically meaningful; FIFO, LIFO, or any other order is acceptable.
