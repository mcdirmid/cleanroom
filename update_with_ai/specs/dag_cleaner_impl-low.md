<!-- Dependencies (md files to read alongside this one):
  - dag_cleaner-low.md
  - dag_storage-low.md
  - dag_clean_logic-low.md
-->

# Implementation LLS: dag_cleaner_impl

## Data Types
```python
from dag_storage import DagStorage, NodeId, NodeMessage, PendingMessages
from dag_clean_logic import DagCleanLogic, CleanResult
from dag_cleaner import DagCleaner, CleaningResult

class DagCleanerImpl(DagCleaner):
    def __init__(self, storage: DagStorage, clean_logic: DagCleanLogic): ...
```

Constructed with `dag_storage` (message persistence and graph access) and `dag_clean_logic` (message processing and dirtiness determination).

## Behavioral Description

`DagCleanerImpl` implements the `DagCleaner` Protocol's `clean_subgraph` operation.

- **`clean_subgraph`** — Returns `(True, CleanResult)` on successful cleaning (no messages, change, or feedback result) or `(False, FailureResult)` on failure (including cycles). Traverses the subgraph in topological order (dependencies before dependents) by following node dependencies through `dag_storage`, validates feedback targets, detects cycles, and applies cleaning with bounds on total invocations (defending against message cycles). On failure: halts immediately without deleting node data. On success: routes change messages to the node's known reverse dependencies (skipping any known reverse dependency that is not in the graph) and feedback messages to the specified dependencies, through `dag_storage`; then, per the result: a `ChangeResult` deletes the node's data (pending messages and known reverse dependencies), a `NoChangeResult` clears the node's pending messages (its known reverse dependencies remain), and a `FeedbackResult` removes no stored data.

- **Failure handling:** Returns a failure result (not deleting node data) when `dag_clean_logic.clean` returns failure; when the total clean count exceeds the bound (`len(subgraph_nodes) * (len(subgraph_nodes) + 1)`); when feedback targets a node outside the subgraph; or when a cycle is detected in the graph topology.
- Messages may be empty strings; multiple identical messages are allowed (no deduplication is performed).

**HLS Justification:** Implements the dag_cleaner interface, using dag_storage and dag_clean_logic.

## Invariants

- No caching; all state reads and writes, including graph access, go through `dag_storage`.
- Subgraph cleaning as a whole is not atomic: successfully cleaned nodes retain their changes even if a later node fails.
- Self-loops (cycles of length 1) are detected during cycle detection.

## Non-Concerns

- **Cycle detection algorithm:** Cycle detection is by topological-sort failure (no topological order exists); the FailureResult returned does not include detail about the detection method.
- **Node ordering within the same topological level:** Any deterministic ordering is acceptable as long as all dependencies are processed before their dependents.
- **Message ordering within a node's pending list:** The order of messages in a node's pending list is not semantically meaningful.
- **FailureResult on failure:** A `FailureResult` is always produced on failure (including self-loops); it carries no detail about the failure.
- **Atomicity of routing+deletion:** Not required; messages are added to routing targets immediately after successful processing, and the node's data is deleted after routing (a change result) or its pending messages cleared (a no-change result); a feedback result removes no stored data.

