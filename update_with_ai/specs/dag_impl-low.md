<!-- Dependencies (md files to read alongside this one):
  - dag-low.md
  - dag_storage-low.md
  - dag_clean_logic-low.md
-->

# Implementation LLS: dag_impl

## Data Types

```python
from dataclasses import dataclass
from dag_storage import DagStorage, NodeId, NodeMessage, PendingMessages
from dag_clean_logic import DagCleanLogic, CleanResult
from dag import Dag, CleaningResult
```

```python
class DagImpl(Dag): ...
```

## Config

```python
@dataclass
class Config:
    storage: DagStorage
    clean_logic: DagCleanLogic
```

**HLS Justification:** The `dag_impl` implementation is configured with `dag_storage` (message persistence and graph access) and `dag_clean_logic` (message processing and dirtiness determination).

## Behavioral Description

`DagImpl` implements the `Dag` Protocol's `clean_subgraph` operation.

- **`clean_subgraph`** — Returns `(True, CleanResult)` on successful cleaning (no messages, change, or feedback result) or `(False, FailureResult)` on failure (including cycles). Traverses the subgraph in topological order (dependencies before dependents) by following node dependencies through `dag_storage`, validates feedback targets, detects cycles, and applies cleaning with bounds on total invocations (defending against message cycles). On failure: halts immediately without deleting node data; on success: routes change messages to the node's known reverse dependencies (skipping any known reverse dependency that is not in the graph) and feedback messages to the specified dependencies, through `dag_storage`, then deletes the node's data.

- **Failure handling:** Returns a failure result (not deleting node data) when `dag_clean_logic.clean` returns failure; when the total clean count exceeds the bound; when feedback targets a node outside the subgraph; or when a cycle is detected in the graph topology.
- Messages may be empty strings; multiple identical messages are allowed (no deduplication is performed).

**HLS Justification:** Implements the dag interface, using dag_storage and dag_clean_logic.

## Invariants

- No caching; all state reads and writes, including graph access, go through `dag_storage`.
- On failure, processing halts immediately; no recovery or retry.
- Cleaning always terminates; the total-cleans bound is `len(subgraph_nodes) * (len(subgraph_nodes) + 1)`.
- Feedback messages are routed only to nodes within the subgraph.
- Self-loops (cycles of length 1) are detected during cycle detection.

## Non-Concerns

- **Cycle detection algorithm:** Cycle detection is by topological-sort failure (no topological order exists); the FailureResult returned does not include detail about the detection method.
- **Node ordering within the same topological level:** Any deterministic ordering is acceptable as long as all dependencies are processed before their dependents.
- **Message ordering within a node's pending list:** The order of messages in a node's pending list is not semantically meaningful.
- **FailureResult on failure:** A `FailureResult` is always produced on failure (including self-loops); it carries no detail about the failure.
- **Atomicity of routing+deletion:** Not required; messages are added to routing targets immediately after successful processing, and the node's data is deleted after routing.

