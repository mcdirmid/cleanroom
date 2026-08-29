<!-- Dependencies (md files to read alongside this one):
  - dag_cleaner_impl.md
  - dag_cleaner.md
  - dag_clean_logic.md
  - build_graph_storage.md
-->

# Implementation LLS: dag_cleaner_asm

## Data Types
```python
from dag_cleaner_impl import DagCleanerImpl
from build_graph_storage import BuildGraphStorage
from dag_clean_logic import DagCleanLogic

class DagCleanerAsm(DagCleanerImpl):
    def __init__(self, storage: BuildGraphStorage, clean_logic: DagCleanLogic) -> None: ...
```

Subclasses `DagCleanerImpl` over a supplied graph storage and clean logic. Fulfills the `DagCleaner` protocol via `DagCleanerImpl`. This assembly performs configuration and assembly only and is never tested.

## Composition

- DagCleanerImpl (DAG cleaning)

## Behavioral Description

- Assembles the concrete DAG cleaner implementation: passes the supplied `BuildGraphStorage` and `DagCleanLogic` directly to `super().__init__`.
- Inherits and implements the `DagCleaner` protocol through `DagCleanerImpl`.
- No functionality beyond configuration and assembly is performed; this assembly is never tested.

## Invariants

- The concrete implementations are selected here, at construction; operations never select components.
- No persistent state is held across calls: each instance is a fresh DAG cleaner.

## Non-Concerns

- **Consumption:** how the assembled DAG cleaner is used is unspecified here.
- **Selection policy:** the concrete implementations wired here are a default assembly; other selections may differ.
