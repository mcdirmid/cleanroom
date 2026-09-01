<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - dag_cleaner.md
  - dag_node_cleaner.md
  - runner_logger.md
  - manifest_node_loader.md
-->

# Interface LLS: build_runner

## Data Types
```python
from typing import Protocol, TypeAlias
from dataclasses import dataclass
from dag_storage import NodeId, MessageContent

ResultSummary: TypeAlias = str

@dataclass(frozen=True)
class BuildResult:
    success: bool
    summary: ResultSummary

class BuildRunner(Protocol):
    def run_cleaning_pass(self, root: NodeId) -> BuildResult: ...
    def mark_node_dirty(self, target: NodeId, message: MessageContent) -> None: ...
    def inject_node_feedback(self, target: NodeId, feedback: MessageContent) -> None: ...
    def broadcast_node_change(self, origin: NodeId, change: MessageContent) -> None: ...
```

- `ResultSummary` → corresponds to build result summary string.
- `BuildResult` → corresponds to *build result*: the final outcome of a *cleaning pass*, reporting overall success or failure.
- `BuildRunner` → corresponds to *build runner*: an orchestration service that executes topological build and cleaning passes across workspace *nodes*.

## Term definitions

- **build result** → the `BuildResult` alias
- **cleaning pass** → term definition: an execution run that cleans dirty *nodes* across a target subgraph
- **build runner** → term definition: an orchestration service that executes topological build and cleaning passes across workspace *nodes*

## Component-Provided Operations

### `run_cleaning_pass`

```python
def run_cleaning_pass(self, root: NodeId) -> BuildResult: ...
```

**Purpose:** (BuildRunner) Executes a complete topological cleaning pass over the acyclic subgraph rooted at a target node.

**Preconditions:**
- `root` is a valid node in the workspace target graph.

**Postconditions:**
- Cleans dirty nodes in topological order using `DagCleaner`.
- Records telemetry events using `RunnerLogger`.
- Returns a `BuildResult` reporting overall pass outcome.

**Failure Handling:** Node failure halts the pass and returns a failing `BuildResult`.

**HLS Justification:** "A *build runner* executes a *cleaning pass* over an acyclic subgraph rooted at a target *node*."

### `mark_node_dirty`

```python
def mark_node_dirty(self, target: NodeId, message: MessageContent) -> None: ...
```

**Purpose:** (BuildRunner) Marks a target node dirty by injecting a change message into its pending queue.

**Preconditions:**
- `target` is a valid node in the storage graph.

**Postconditions:**
- Adds a change message carrying `message` to `target`'s pending messages and marks it dirty.

**Failure Handling:** Always succeeds when preconditions are met.

**HLS Justification:** "A *build runner* marks a target *node* dirty by injecting a non-triggering check *change message*."

### `inject_node_feedback`

```python
def inject_node_feedback(self, target: NodeId, feedback: MessageContent) -> None: ...
```

**Purpose:** (BuildRunner) Injects feedback into a target node's message queue, marking it dirty for cleaning.

**Preconditions:**
- `target` is a valid node in the storage graph.

**Postconditions:**
- Adds a feedback message carrying `feedback` to `target`'s pending messages and marks it dirty.

**Failure Handling:** Always succeeds when preconditions are met.

**HLS Justification:** "A *build runner* injects a caller-supplied *feedback message* into a target *node*."

### `broadcast_node_change`

```python
def broadcast_node_change(self, origin: NodeId, change: MessageContent) -> None: ...
```

**Purpose:** (BuildRunner) Broadcasts a change message from an origin node to all of its reverse dependencies and marks them dirty.

**Preconditions:**
- `origin` is a valid node in the storage graph.

**Postconditions:**
- Adds a change message carrying `change` to the pending queues of all reverse dependencies of `origin` and marks them dirty.

**Failure Handling:** Always succeeds when preconditions are met.

**HLS Justification:** "A *build runner* broadcasts a caller-supplied *change message* from a *node* to all of its reverse dependencies."

## Invariants

- A cleaning pass halts immediately when any dirty node fails to clean.
- The build result captures aggregate summary and overall success state.
