<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - dag_node_cleaner.md
  - dag_cleaner.md
-->

# Implementation LLS: dag_cleaner_impl

## Data Types
```python
from dag_cleaner import DagCleaner

class DagCleanerImpl(DagCleaner):
    def __init__(self, max_iterations: int = 100) -> None: ...
```

## Behavioral Description

- `DagCleanerImpl` computes topological order across reachable dependency nodes from `root`.
- Cleans dirty nodes in topological order, ensuring each node is cleaned only when all of its dependencies are clean.
- A cleaned node with change messages broadcasts those messages to its recorded reverse dependencies in `DagStorage`, then clears its node data.
- A cleaned node with feedback messages routes them to target dependencies and retains its data in `DagStorage`.
- Re-evaluates node dirty states until all nodes in the subgraph are clean or execution exceeds `max_iterations`.
- When cleaning exceeds `max_iterations`, halts pass execution with an unexpected failure.

## Invariants

- Cleaning is sequential per topological layer.
