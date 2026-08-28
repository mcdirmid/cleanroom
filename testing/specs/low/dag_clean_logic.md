<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - tool_provider.md
-->

# Interface LLS: dag_clean_logic

## Data Types
```python
from dag_storage import NodeId, PendingMessages, NodeMessage
from tool_provider import TerminateSuccessResult
from typing import Protocol, Union, Literal, TypeAlias
from dataclasses import dataclass

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

CleanResult: TypeAlias = Union[ChangeResult, FeedbackResult, NoChangeResult, FailureResult]

class DagCleanLogic(Protocol):
    def clean(self, node_id: NodeId, messages: PendingMessages) -> CleanResult: ...
    def is_dirty(self, node_id: NodeId, pending_messages: PendingMessages) -> bool: ...
```

- `ChangeResult` (change): messages to broadcast to all reverse dependencies (nodes that depend on this node); its messages carry the `change` kind
- `FeedbackResult` (feedback): messages to deliver to specific dependencies (tuples of target node and message); its messages carry the `feedback` kind
- `NoChangeResult` (no change): node cleaned successfully, no messages produced
- `FailureResult` (failure): cleaning failed, no messages produced

`ChangeResult`, `FeedbackResult`, and `NoChangeResult` extend the `TerminateSuccessResult` protocol from `tool_provider`, so a successful termination signal can carry a clean result directly.

## Term definitions

- **dirty** → term definition: the state of requiring cleaning; a node is dirty when it has pending messages or custom conditions hold, and a node becomes dirty when it receives a change or a feedback message
- **cleaning** → term definition: processing a node may produce zero or more messages for delivery
- **change message** → term definition: a message of kind `change` (the `NodeMessage` type from dag_storage) that informs reverse dependencies how the source node changed
- **feedback message** → term definition: a message of kind `feedback` (the `NodeMessage` type from dag_storage) that informs a specific dependency how it must be updated so cleaning can proceed past the node; a feedback message targets exactly one dependency of the source node, and multiple feedback messages may be produced during a single cleaning, each delivered individually
- **node** → the `NodeId` alias from dag_storage
- **dependency** → the `NodeDependencies` alias from dag_storage
- **pending message** → the `PendingMessages` alias from dag_storage
- **message kind** → the `MessageKind` alias from dag_storage
- **termination result** → the `TerminateSuccessResult` type from tool_provider

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
- When `messages` includes a feedback message, provides no `NoChangeResult`: the cleaning produces a `ChangeResult`, a `FeedbackResult`, or a `FailureResult`.

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

**Failure Handling:** No expected failures; the query signals dirtiness or not. The only caller obligation is the precondition that `node_id` exists in the graph; violations are unexpected, and the interface does not prescribe violation behavior.

**HLS Justification:** "The client may query whether a node is dirty."


## Invariants

- On failure, no messages are produced.
- A node produces either change or feedback messages, not both.


## Non-Concerns

- **Error propagation details:** How errors propagate between components is unspecified.

