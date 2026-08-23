<!-- Dependencies (md files to read alongside this one):
  - dag_storage-low.md
  - tool_provider-low.md
-->

# Interface LLS: dag_clean_logic

## Data Types
```python
from __future__ import annotations

from typing import Protocol, Sequence, TypeAlias
from dag_storage import DagNode, NodeMessage
from tool_provider import TerminationResult

ChangeMessage: TypeAlias = str
FeedbackMessage: TypeAlias = str
RoutingIntent: TypeAlias = str

class DagCleanLogic(Protocol):
    def clean_node(self, node: DagNode, pending_messages: Sequence[NodeMessage]) -> tuple[str, TerminationResult, Sequence[ChangeMessage], Sequence[FeedbackMessage]]: ...
    def is_dirty(self, node: DagNode) -> bool: ...
```

- **DagNode**: the node identifier, reused from dag_storage.
- **ChangeMessage**: a message informing reverse dependencies how the source node changed.
- **FeedbackMessage**: a message informing a specific dependency how it must be updated so cleaning can proceed past the source node. A feedback message targets exactly one dependency of the source node; multiple feedback messages may be produced during a single cleaning, each delivered individually.
- **RoutingIntent**: which kind of message is produced and toward whom; routing itself is the consuming component's responsibility.
- **TerminationResult**: the outcome of a successfully terminated session, per tool_provider (completed with no changes, completed with changes to propagate, or attributed to dependencies with feedback for correction).
- **DagCleanLogic**: the protocol capturing the dag_clean_logic interface.
- **Dirty**: the state of requiring cleaning. A node is dirty when it has pending messages or custom conditions hold; a node becomes dirty when it receives a change or a feedback message. Custom conditions may flag a node dirty with no pending messages.
- **Cleaning**: the process of consuming a node's pending messages and producing new messages. A node that produces no messages on being cleaned was successfully cleaned but did not change.

## Component-Provided Operations

Terms (cross-cutting behavioral rules):

- **pending message**: A message delivered to a node and not cleaned since delivery.
- **dependency**: A node A depends on node B means A has an outgoing edge to B.
- **routing intent**: which kind of message is produced and toward whom; routing itself is the consuming component's responsibility.

### `clean_node`

```python
def clean_node(self, node: DagNode, pending_messages: Sequence[NodeMessage]) -> tuple[str, TerminationResult, Sequence[ChangeMessage], Sequence[FeedbackMessage]]: ...
```

**Purpose:** Consume a node's pending messages and produce new messages (change or feedback).

**Preconditions:** The node exists in the graph (has been declared or accessed before). The node has pending messages, or custom conditions hold.

**Postconditions:**
- Success is signaled only after fully processing all messages.
- On success: all pending messages are consumed; zero or more change messages or zero or more feedback messages are produced for delivery. A node produces either change messages or feedback messages during a single cleaning, not both. Producing a feedback message indicates a dependency must be fixed; the current node is cleaned again after the dependency sends a change message.
- On failure: no messages are produced; pending messages are left unchanged.
- A successful cleaning result (change, feedback, or no-change) is a termination result per tool_provider: a successful termination signal may carry it.
- Produced messages are valid for delivery.

**Failure Handling:** Returns a failure signal (no messages produced) when unable to process; pending messages remain unchanged.

**HLS Justification:** "Invoke cleaning on a node with its pending messages" (Contract, Operations).

### `is_dirty`

```python
def is_dirty(self, node: DagNode) -> bool: ...
```

**Purpose:** Determine whether a node is dirty (requires cleaning).

**Preconditions:** The node exists in the graph (has been declared or accessed before).

**Postconditions:** Returns `True` when the node has pending messages or custom conditions hold; `False` otherwise.

**Failure Handling:** No expected failures.

**HLS Justification:** "Query whether a node is dirty" (Contract, Operations).

## Invariants

- None. All guarantees are captured in the individual operation postconditions.
