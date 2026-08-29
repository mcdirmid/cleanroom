<!-- Dependencies (md files to read alongside this one):
  - build_runner_impl.md
  - build_graph_storage_impl.md
  - agent_node_clean_logic_asm.md
  - dag_cleaner_asm.md
  - build_runner.md
-->

# Implementation LLS: build_asm

## Data Types
```python
from build_runner_impl import BuildRunnerImpl

class BuildAsm(BuildRunnerImpl):
    def __init__(self) -> None: ...
```

Subclasses `BuildRunnerImpl` with pre-wired factories: the graph factory wraps
`BuildGraphStorageFileImpl`, the clean-logic factory wraps `AgentNodeCleanLogicAsm`,
and the DAG factory wraps `DagCleanerAsm`. Fulfills the `BuildRunner` protocol via
`BuildRunnerImpl`. This assembly performs configuration and assembly only and is
never tested.

## Composition

- BuildGraphStorageFileImpl (graph storage)
- AgentNodeCleanLogicAsm (agent clean logic assembly)
- DagCleanerAsm (DAG cleaner assembly)
- BuildRunnerImpl (build runner implementation)

## Behavioral Description

- Assembles the concrete implementations and sub-assemblies at construction: passes the graph factory (`BuildGraphStorageFileImpl`), clean-logic factory (`AgentNodeCleanLogicAsm`), and DAG factory (`DagCleanerAsm`) to `super().__init__`.
- Inherits and implements the `BuildRunner` protocol through `BuildRunnerImpl`.
- No functionality beyond configuration and assembly is performed; this assembly is never tested.

## Invariants

- The concrete implementations are selected here, at construction; the runner's operations never select components.
- No persistent state is held across calls: each instance is a fresh runner.

## Non-Concerns

- **Consumption:** how the assembled runner is used (entry points, generated wrappers) is unspecified here.
- **Selection policy:** the concrete implementations wired here are a default assembly; other selections may differ.
