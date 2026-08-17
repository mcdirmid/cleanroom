<!-- Dependencies (md files to read alongside this one):
  - dag_storage-low.md
  - tool_provider-low.md
-->

# Interface LLS: dag_clean_logic

## Data Types

```python
from dag_storage import NodeId, PendingMessages, NodeMessage
from tool_provider import TerminateSuccessResult
from typing import Protocol, Union, Literal
from dataclasses import dataclass
```

```python
@dataclass
class ChangeResult(TerminateSuccessResult):
    messages: list[NodeMessage]
    type: Literal["change"] = "change"

@dataclass
class FeedbackResult(TerminateSuccessResult):
    messages: list[tuple[NodeId, NodeMessage]]
    type: Literal["feedback"] = "feedback"

@dataclass
class NoChangeResult(TerminateSuccessResult):
    type: Literal["no_change"] = "no_change"

@dataclass
class FailureResult:
    type: Literal["failure"] = "failure"

CleanResult = Union[ChangeResult, FeedbackResult, NoChangeResult, FailureResult]
```

- `ChangeResult` (change): messages to broadcast to all reverse dependencies (nodes that depend on this node)
- `FeedbackResult` (feedback): messages to deliver to specific dependencies (tuples of target node and message)
- `NoChangeResult` (no change): node cleaned successfully, no messages produced
- `FailureResult` (failure): cleaning failed, no messages produced

`ChangeResult`, `FeedbackResult`, and `NoChangeResult` extend the `TerminateSuccessResult` protocol from `tool_provider`, so a successful termination signal can carry a clean result directly.

```python
class DagCleanLogic(Protocol):
    def clean(self, node_id: NodeId, messages: PendingMessages) -> CleanResult: ...
    def is_dirty(self, node_id: NodeId, pending_messages: PendingMessages) -> bool: ...
```

## Component-Provided Operations

### `clean`

```python
def clean(self, node_id: NodeId, messages: PendingMessages) -> CleanResult
```

**Purpose:** Process a node's pending messages and produce new messages.

**Preconditions:** `node_id` must exist in the graph; graph topology is accessible. `messages` may be empty (the node may be cleaned with no pending messages when flagged dirty by custom conditions).

**Postconditions:**
- On success: provides `ChangeResult` (broadcast messages to reverse dependencies), `FeedbackResult` (deliver messages to specific dependencies), or `NoChangeResult` (no messages)
- On success, all pending messages were processed
- Produced messages are valid for delivery
- On failure: provides `FailureResult`
- Produces either change or feedback messages, not both.
- Caller routes change messages to reverse dependencies; feedback messages to specified dependencies.

**Failure Handling:**
- On failure, provides `FailureResult`; no messages are produced and pending messages remain unchanged.

**HLS Justification:** "The client may invoke cleaning on a node with its pending messages."

### `is_dirty`

```python
def is_dirty(self, node_id: NodeId, pending_messages: PendingMessages) -> bool
```

**Purpose:** Determine if a node requires cleaning.

**Preconditions:** `node_id` must exist in the graph; graph topology is accessible.

**Postconditions:** Signals dirtiness if:
- The node has pending messages, or
- Custom dirtiness conditions defined by the implementation hold (e.g., the node's writable output files do not exist on disk)

**HLS Justification:** "The client may query whether a node is dirty."


## Invariants

- On failure, no messages are produced.
- A node produces either change or feedback messages, not both.


## Non-Concerns

- **Error propagation details:** How errors propagate between components is unspecified.

