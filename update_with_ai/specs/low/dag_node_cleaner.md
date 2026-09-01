<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
-->

# Interface LLS: dag_node_cleaner

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Optional, Union
from dag_storage import NodeId, PendingMessage, DagMessage

ChangeMessage: TypeAlias = DagMessage
FeedbackMessage: TypeAlias = DagMessage

NodeCleaningOutcome: TypeAlias = Optional[Sequence[Union[ChangeMessage, FeedbackMessage]]]

class NodeCleaner(Protocol):
    def clean_node(self, node: NodeId, pending_messages: Sequence[PendingMessage]) -> NodeCleaningOutcome: ...
```

- `ChangeMessage` → corresponds to *change message*: a message produced by cleaning a *node*, communicating modifications to downstream dependents.
- `FeedbackMessage` → corresponds to *feedback message*: a message produced by cleaning a *node*, communicating issues to upstream dependencies.
- `NodeCleaningOutcome` → corresponds to outcome produced by cleaning a node.
- `NodeCleaner` → corresponds to *node cleaner*: a service that cleans an individual *node* using its *pending messages*.

## Term definitions

- **change message** → the `ChangeMessage` alias
- **feedback message** → the `FeedbackMessage` alias
- **node cleaner** → term definition: a service that cleans an individual *node* using its *pending messages*

## Component-Provided Operations

### `clean_node`

```python
def clean_node(self, node: NodeId, pending_messages: Sequence[PendingMessage]) -> NodeCleaningOutcome: ...
```

**Purpose:** (NodeCleaner) Cleans a single dirty node given its pending messages.

**Preconditions:**
- `node` is a valid node in the graph storage.

**Postconditions:**
- Returns `Sequence[ChangeMessage]` if the node produced changes for downstream reverse dependencies.
- Returns `Sequence[FeedbackMessage]` if the node attributed issues to upstream dependencies.
- Returns `None` if the node succeeded with no modifications or messages.

**Failure Handling:** Cleaning failure leaves the node dirty and returns no messages.

**HLS Justification:** "A *node cleaner* cleans a dirty *node* using its *pending messages*, producing *change messages* for downstream dependents or *feedback messages* for upstream dependencies."

## Invariants

- A node cleaning produces either change messages or feedback messages during a single cleaning, not both.
- A failed cleaning produces no messages and leaves the node dirty.
