<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - dag_node_cleaner.md
-->

# Interface LLS: dag_cleaner

## Data Types
```python
from typing import Protocol
from dag_storage import DagStorage, NodeId
from dag_node_cleaner import NodeCleaner

class DagCleaner(Protocol):
    def clean_subgraph(self, root: NodeId, storage: DagStorage, cleaner: NodeCleaner) -> None: ...
```

- `DagCleaner` → corresponds to *dag cleaner*: an orchestration service that cleans subgraphs in a *dag storage* using a *node cleaner*.

## Term definitions

- **dag cleaner** → term definition: an orchestration service that cleans subgraphs in a *dag storage* using a *node cleaner*

## Component-Provided Operations

### `clean_subgraph`

```python
def clean_subgraph(self, root: NodeId, storage: DagStorage, cleaner: NodeCleaner) -> None: ...
```

**Purpose:** (DagCleaner) Cleans an acyclic subgraph rooted at a target node in topological order.

**Preconditions:**
- The subgraph rooted at `root` must be acyclic.

**Postconditions:**
- Dirty nodes are cleaned in strict dependency-first topological order.
- Routes change messages produced by cleaned nodes to downstream reverse dependencies.
- Routes feedback messages produced by cleaned nodes to upstream dependencies.

**Failure Handling:** Node cleaning failures halt pass execution and leave incomplete nodes dirty.

**HLS Justification:** "A *dag cleaner* can clean an acyclic subgraph rooted at a target *node* in a *dag storage*."

## Invariants

- Dependencies are guaranteed clean before dependent nodes execute.
- Routing change and feedback messages marks affected destination nodes dirty.
