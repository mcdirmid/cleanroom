<!-- Dependencies (md files to read alongside this one):
  - tool_provider-low.md
-->

# Interface LLS: bazel_node_loader

## Data Types

```python
from dataclasses import dataclass
from typing import Protocol
from tool_provider import ToolProvider
```

```python
@dataclass
class BazNode(ToolProvider):
    label: str
    prompt: str
    tools: list[str]
    deps: list[str]
    silent_deps: list[str]
    srcs: list[str]
    silent_srcs: list[str]
```

A data class Protocol that bundles static node metadata with the `ToolProvider` interface. Internal state fields (e.g., `_dependency_nodes`, `_agent_loop`) are implementation-specific and defined in the implementation spec. A loaded node resolves tool definitions and tool execution from the tool providers declared in its manifest; a tool call that no declared provider handles signals a tool failure.

**HLS Justification:** "Designates a runtime representation of a Bazel node."

```python
class BazelNodeLoader(Protocol):
    def load_node(self, label: str) -> BazNode | None: ...
    def load_graph(self, root_label: str) -> dict[str, BazNode]: ...
    def get_node_prompt(self, node_label: str) -> str | None: ...
```

## Component-Provided Operations

### `load_node`

```python
def load_node(self, label: str) -> BazNode | None
```

**Purpose:** Load a single node from its manifest.

**Preconditions:** None.

**Postconditions:** Returns a `BazNode` with manifest data and tool-provider capability, or `None` if not found.

**Failure Handling:** Returns `None` for unknown labels.

**HLS Justification:** "The client may load a node by label."

### `load_graph`

```python
def load_graph(self, root_label: str) -> dict[str, BazNode]
```

**Purpose:** Load all nodes in the subgraph rooted at `root_label`.

**Preconditions:** None.

**Postconditions:** Returns all nodes (root and transitive deps, including silent_deps).

**Failure Handling:** Unknown labels are omitted from the loaded graph.

**HLS Justification:** "The client may load a subgraph rooted at a label."

### `get_node_prompt`

```python
def get_node_prompt(self, node_label: str) -> str | None
```

**Purpose:** Get the prompt for a specific node.

**Postconditions:** Returns the node's prompt or `None` if not found.

**Failure Handling:** Returns `None` for unknown labels.

**HLS Justification:** "The client may query a node's prompt."


## Invariants

- Nodes are cached by label; repeated loads of the same label return the cached instance.
- Partial loads do not populate the cache; a node is cached only after successful deserialization.
- Manifest file paths are derived deterministically from labels.


## Non-Concerns

- **Cache eviction policy:** Whether and when the cache evicts entries is unspecified.
- **Manifest resolution algorithm:** The exact mechanism for resolving a label to a manifest file (e.g., `//pkg:target` → `pkg/target_manifest.json` or the `RUNFILES_DIR` environment variable) is unspecified.

