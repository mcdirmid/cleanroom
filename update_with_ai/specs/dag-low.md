<!-- Dependencies (md files to read alongside this one):
  - dag_storage-low.md
  - dag_clean_logic-low.md
-->

# Interface LLS: dag

## Data Types

```python
from typing import Protocol
from dag_storage import NodeId
from dag_clean_logic import CleanResult
```

```python
CleaningResult = tuple[bool, CleanResult]
```

Represents the outcome of cleaning: `(True, success)`, `(True, change_result)`, `(True, feedback_result)`, or `(False, failure_result)`.

```python
class Dag(Protocol):
    def clean_subgraph(self, target_node: NodeId) -> CleaningResult: ...
```

## Component-Provided Operations

### `clean_subgraph`

```python
def clean_subgraph(self, target_node: NodeId) -> CleaningResult
```

**Purpose:** Clean all dirty nodes in the subgraph rooted at `target_node` (the target node and all nodes reachable through its direct and indirect dependencies, as defined in `dag_storage-low.md`) until none remain.

**Preconditions:**
- `target_node` exists in the graph.
- The graph topology, as provided through `dag_storage`, does not change during cleaning.
- No concurrent calls (undefined behavior).
- No node receives a message while being cleaned (undefined behavior).

**Postconditions:**
- All dirty nodes in the subgraph are cleaned.
- Nodes that become dirty during cleaning are processed before completion.
- Cleaning proceeds in topological order (dependencies before dependents).
- A node is not cleaned while any dependency is dirty.
- Each node's cleaning is atomic (it provides messages or signals failure, never both).
- Change messages delivered to all known reverse dependencies of the node (as provided by `dag_storage`); feedback messages delivered to specified dependencies (within the subgraph).
- Cleaning always terminates (guarded by a single total bound on clean operations).
- Returns `(True, CleanResult)` on success (indicating no messages, a `ChangeResult`, or a `FeedbackResult`); otherwise `(False, FailureResult)` where the `CleanResult` variant is a `FailureResult`.
- On failure: the offending node's messages remain unchanged; previously cleaned nodes retain changes; processing halts.

**Failure Handling:**
- If the graph topology contains a cycle, returns `(False, FailureResult)`; state is unchanged (no node data deleted, no messages routed).
- If feedback targets a node outside the subgraph, returns `(False, FailureResult)`; the offending node's messages remain unchanged and processing halts.

**HLS Justification:** "The client may request cleaning of a subgraph rooted at a target node."


## Invariants

- Only nodes in the subgraph are cleaned; nodes outside may receive messages but are not cleaned.
- Topological sort is computed once and remains fixed.
- Cleaning always terminates (bounded by a single total bound on clean operations).
- No cross-restart state: all state is per-run; nodes are dirty from message delivery until cleaned.


## Non-Concerns

- **Cycle-detection algorithm:** The algorithm used to detect cycles (e.g., topological sort failure vs. explicit DFS) is unspecified. The returned FailureResult does not include an error message specifying whether the cycle was detected (e.g., by topological sort failure) or any other detail.

