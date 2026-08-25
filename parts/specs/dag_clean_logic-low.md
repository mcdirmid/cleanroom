<!-- Dependencies (md files to read alongside this one):
  - dag_storage-low.md
  - tool_provider-low.md
-->

# Interface LLS: dag_clean_logic

## Data Types

```python
from typing import Protocol, Sequence, TypeAlias

from dag_storage import NodeName, MessageContent, PendingMessage
from tool_provider import TerminationResult

ChangeMessage: TypeAlias = MessageContent
FeedbackMessage: TypeAlias = MessageContent


class DagCleanLogic(Protocol):
    def is_dirty(self, node: NodeName) -> bool: ...
    def clean(self, node: NodeName, messages: Sequence[PendingMessage]) -> tuple[list[ChangeMessage] | list[FeedbackMessage] | None, TerminationResult | None]: ...
```

**ChangeMessage:** A message informing a reverse dependency how the source node changed.

**FeedbackMessage:** A message informing a specific dependency how it must be updated so cleaning can proceed past the source node. Targets exactly one dependency.

## Term definitions

- **node** → the `NodeName` alias from dag_storage
- **pending message** → the `PendingMessage` alias from dag_storage
- **dependency** → the `DependencyName` alias from dag_storage
- **change message** → the `ChangeMessage` alias
- **feedback message** → the `FeedbackMessage` alias
- **dirty** → a state indicating a node requires cleaning; a node is dirty when it has pending messages or custom conditions hold
- **cleaning** → the processing of a node which may produce zero or more messages for delivery
- **termination result** → the `TerminationResult` alias from tool_provider

## Component-Provided Operations

### `is_dirty`

```python
def is_dirty(self, node: NodeName) -> bool: ...
```

**Purpose:** Query whether a node is dirty (requires cleaning).

**Preconditions:** The node exists in the graph.

**Postconditions:** Returns `True` if the node has pending messages or custom conditions hold; returns `False` otherwise.

**Failure Handling:** None expected.

**HLS Justification:** Contract — "Query whether a node is dirty." Guarantees — "Signals dirtiness when the node has pending messages or custom conditions hold."

### `clean`

```python
def clean(self, node: NodeName, messages: Sequence[PendingMessage]) -> tuple[list[ChangeMessage] | list[FeedbackMessage] | None, TerminationResult | None]: ...
```

**Purpose:** Invoke cleaning on a node with its pending messages.

**Preconditions:** The node exists in the graph.

**Postconditions:** On success: returns zero or more messages for delivery and a `TerminationResult` when all pending messages have been processed. On failure: returns `(None, None)` with pending messages unchanged and no messages produced. A successful cleaning produces either change messages or feedback messages, never both. Producing a feedback message follows the `feedback message` term: the current node is cleaned again after the dependency sends a change message. Produced messages are valid for delivery.

**Failure Handling:** Returns `(None, None)` when unable to process the node.

**HLS Justification:** Contract — "Invoke cleaning on a node with its pending messages." Guarantees — success signaling, failure behavior, message production rules, and termination result mapping.

## Invariants

- A cleaning operation produces either change messages or feedback messages, never both.
- Produced messages are valid for delivery.

## Non-Concerns

- **Error propagation details:** how failures propagate between components is unspecified — the HLS states this as a non-concern.
- **Storage failures:** assumed not to occur — behavior is undefined if they do (inherited from dag_storage).
- **Dependency identification:** the component assumes it can identify a node's dependencies from the graph topology via dag_storage.
