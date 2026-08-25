<!-- Dependencies (md files to read alongside this one):
  - dag_storage-low.md
  - dag_clean_logic-low.md
-->

# Interface LLS: dag

## Data Types

```python
from typing import Protocol
from dag_storage import NodeName, PendingMessage, DependencyName
from dag_clean_logic import ChangeMessage, FeedbackMessage

class DagCleaner(Protocol):
    def clean(self, target: NodeName) -> None: ...
```

**NodeName:** A string identifying a vertex in the DAG graph (from dag_storage).

**PendingMessage:** A message that has been delivered to a node and not yet cleaned (from dag_storage).

**DependencyName:** A node A depends on B means A has an outgoing edge to B (from dag_storage).


**ChangeMessage:** A message informing a reverse dependency how the source node changed (from dag_clean_logic).

**FeedbackMessage:** A message informing a specific dependency how it must be updated so cleaning can proceed past the source node. Targets exactly one dependency (from dag_clean_logic).

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

## Component-Provided Operations

### `clean`

```python
def clean(self, target: NodeName) -> None: ...
```

**Purpose:** Request cleaning of the subgraph rooted at a target node.

**Preconditions:** The target node exists in the graph. The graph topology does not change during cleaning. No concurrent cleaning operations are initiated. No node receives a message while it is being cleaned.

**Postconditions:** Cleans every dirty node in the subgraph rooted at the target node, routing change messages to reverse dependencies and feedback messages to specific dependencies, so that no dirty nodes remain. Each node's cleaning is atomic. Produces no direct output; messages are routed to node stores via dag_storage. A node may be cleaned multiple times in one operation; feedback delivered to a previously cleaned node re-dirties it within the same operation. Nodes outside the subgraph may receive messages and become dirty, but are not cleaned until a subgraph containing them is cleaned.

**Failure Handling:** Signals failure, leaving the offending node's messages unchanged and halting cleaning, in the following cases:
- A node's cleaning fails — leaves the offending node's messages unchanged and halts cleaning.
- Message delivery would otherwise continue cleaning without bound — halts cleaning.
- Feedback targets a node outside the subgraph — feedback is delivered only within the subgraph; halts cleaning.
- A graph cycle is detected — signals failure, leaving state unchanged.

**HLS Justification:** Contract → Operations → "Request cleaning of the subgraph rooted at a target node."

## Invariants

- Cleaning is topological: it follows a fixed topological order for the operation; a node is cleaned only while none of its dependencies are dirty; after each cleaning, dirtiness is re-evaluated for all nodes; cleaning stops when no node remains dirty.
- Cleaning always terminates, bounded by a single total bound on clean operations.
- All state is per-run; no state persists across restarts.

## Non-Concerns

- **Cycle detection:** the algorithm used to detect cycles is unspecified — cycle detection is a detail that does not affect the correctness of the cleaning process.
