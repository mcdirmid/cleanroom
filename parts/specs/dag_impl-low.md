<!-- Dependencies (md files to read alongside this one):
  - dag-low.md
  - dag_storage-low.md
  - dag_clean_logic-low.md
  - tool_provider-low.md
-->

# Implementation LLS: dag_impl

## Data Types

```python
from dag import DagCleaner

class DagImpl(DagCleaner): ...
```

**DagCleaner:** The interface that DagImpl fulfills.

**DagImpl:** The concrete implementation class fulfilling the `DagCleaner` interface.

## Term definitions

- **node** → the `NodeName` alias from dag_storage
- **dependency** → the `DependencyName` alias from dag_storage
- **pending message** → the `PendingMessage` alias from dag_storage
- **subgraph** → term definition from dag_storage: a target node (included) plus all nodes reachable through its direct and indirect dependencies
- **reverse dependency** → term definition from dag_storage: A node recorded as depending on another node. Recording happens when a node retrieves a dependency, at most once per dependency, and only for its propagating dependencies (repeated retrievals add no duplicates).
- **dirty** → term definition from dag_clean_logic: a state indicating a node requires cleaning; a node is dirty when it has pending messages or custom conditions hold
- **cleaning** → term definition from dag_clean_logic: the processing of a node which may produce zero or more messages for delivery
- **change message** → the `ChangeMessage` alias
- **feedback message** → the `FeedbackMessage` alias
- **message** → the `MessageContent` alias from dag_storage
- **termination result** → the `TerminationResult` alias from tool_provider

## Behavioral Description

**`clean`** — Request cleaning of the subgraph rooted at a target node. Preconditions: the target node exists in the graph, the graph topology does not change during cleaning, no concurrent cleaning operations are initiated, no node receives a message while it is being cleaned.

Behavior: Re-evaluates dirtiness for each node in the subgraph (rooted at the target) in a fixed topological order. For each node, calls `is_dirty` from dag_clean_logic; if the node is dirty, calls `clean(node, messages)` from dag_clean_logic to process its pending messages. The clean logic returns either change messages or feedback messages (never both), or `(None, None)` on failure. Change messages are broadcast to all known reverse dependencies present in the graph; a known reverse dependency not in the graph (unresolvable) is skipped. Feedback messages are delivered to the specific dependency they target within the subgraph. After routing messages for each node, the node's data (pending messages and known reverse dependencies) is deleted via dag_storage's `delete_node`. Routing reads the node's known reverse dependencies before deletion, ensuring they are still present. After each cleaning, dirtiness is re-evaluated for all nodes; if feedback re-dirties a previously cleaned node, that node is cleaned again within the same operation. Cleaning stops when no node remains dirty. No internal state; all state is delegated to dag_storage. All reads and writes, including graph access, go through dag_storage without caching.

Failure handling: Signals failure, leaving the offending node's messages unchanged and halting cleaning, in the following cases:
- A node's cleaning fails — leaves the offending node's messages unchanged and halts cleaning.
- Message delivery would otherwise continue cleaning without bound — halts cleaning.
- Feedback targets a node outside the subgraph — feedback is delivered only within the subgraph; halts cleaning.
- A graph cycle is detected (including self-loops) — signals failure, leaving state unchanged.

Subgraph cleaning is not atomic: successfully cleaned nodes retain their changes even if a later node fails.

## Invariants

- Empty strings are valid messages.
- Messages are discrete items; multiple identical messages are allowed (no deduplication is performed).

## Non-Concerns

- **Ordering among nodes at the same topological level:** any deterministic order is acceptable as long as dependencies are processed before dependents — the HLS states this as a non-concern.
- **Message ordering:** the order of messages in a node's pending list is not semantically meaningful; FIFO, LIFO, or any other order is acceptable — the HLS states this as a non-concern.
- **Cycle detection algorithm:** the algorithm used to detect cycles is unspecified — cycle detection is a detail that does not affect the correctness of the cleaning process.
- **Storage failures:** assumed not to occur — behavior is undefined if they do (inherited from dag_storage).
- **Concurrent cleaning:** concurrent cleaning operations, or a message arriving during cleaning, result in undefined behavior — the HLS states this as a failure non-concern.
