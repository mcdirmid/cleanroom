<!-- Dependencies (md files to read alongside this one):
  - virtual_file_name.md
  - dag_storage.md
  - sandbox.md
  - build_agent_config.md
-->

# Interface LLS: build_graph_storage

## Data Types
```python
from typing import Protocol, TypeAlias, Optional
from dataclasses import dataclass
from dag_storage import DagStorage, NodeId
from sandbox import SandboxConfig
from build_agent_config import ConfigTarget

TaskPrompt: TypeAlias = str

@dataclass(frozen=True)
class NodeDefinition:
    sandbox_config: SandboxConfig
    prompt: Optional[TaskPrompt] = None
    config_target: Optional[ConfigTarget] = None

class BuildGraphStorage(DagStorage, Protocol):
    def get_sandbox_config(self, node: NodeId) -> SandboxConfig: ...
    def get_task_prompt(self, node: NodeId) -> Optional[TaskPrompt]: ...
    def get_node_definition(self, node: NodeId) -> Optional[NodeDefinition]: ...
```

- `TaskPrompt` → corresponds to *task prompt*: an instruction describing the work required to clean a *node*.
- `NodeDefinition` → corresponds to *node definition*: metadata describing target *sandbox configurations*, *task prompts*, *config targets*, guides, verification checks, and dependency blame mappings for a *node*.
- `BuildGraphStorage` → corresponds to *build graph storage*: a *dag storage* backed by workspace build target manifests.

## Term definitions

- **task prompt** → the `TaskPrompt` alias
- **node definition** → the `NodeDefinition` alias
- **build graph storage** → term definition: a *dag storage* backed by workspace build target manifests

## Component-Provided Operations

### `get_sandbox_config`

```python
def get_sandbox_config(self, node: NodeId) -> SandboxConfig: ...
```

**Purpose:** (BuildGraphStorage) Retrieves the sandbox configuration (file permissions, templates, mappings) for a specific workspace node.

**Preconditions:**
- `node` is a valid node in the storage graph.

**Postconditions:**
- Returns the complete `SandboxConfig` declared for the target node.

**Failure Handling:** Always succeeds when preconditions are met.

**HLS Justification:** "A *build graph storage* provides *task prompts*, *node definitions*, and *sandbox configurations* for declared *nodes*."

### `get_task_prompt`

```python
def get_task_prompt(self, node: NodeId) -> Optional[TaskPrompt]: ...
```

**Purpose:** (BuildGraphStorage) Retrieves the declared task prompt for a specific workspace node.

**Preconditions:**
- `node` is a valid node in the storage graph.

**Postconditions:**
- Returns the declared `TaskPrompt` for the target node, or `None` if no prompt was configured.

**Failure Handling:** Always succeeds when preconditions are met.

**HLS Justification:** "A *build graph storage* provides *task prompts*, *node definitions*, and *sandbox configurations* for declared *nodes*."

### `get_node_definition`

```python
def get_node_definition(self, node: NodeId) -> Optional[NodeDefinition]: ...
```

**Purpose:** (BuildGraphStorage) Retrieves the complete node definition for a declared workspace node.

**Preconditions:**
- `node` is a valid node in the storage graph.

**Postconditions:**
- Returns the declared `NodeDefinition` for the target node, or `None` if undefined.

**Failure Handling:** Always succeeds when preconditions are met.

**HLS Justification:** "A *build graph storage* provides *task prompts*, *node definitions*, and *sandbox configurations* for declared *nodes*."

## Invariants

- Sandbox configurations provide disjoint read-write permissions across independent targets.
