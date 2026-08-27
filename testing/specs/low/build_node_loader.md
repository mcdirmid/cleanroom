<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - sandbox.md
-->

# Interface LLS: build_node_loader

## Data Types
```python
from dataclasses import dataclass, field
from typing import Protocol
from tool_provider import ToolProvider

@dataclass
class BuildNode(ToolProvider):
    label: str
    prompt: str
    tools: list[str]
    deps: list[str]
    silent_deps: list[str]
    src: str = ""
    template: str | None = None
    guide: str | None = None
    silent_srcs: list[str] = field(default_factory=list)
    feedback_deps: list[str] = field(default_factory=list)

class BuildNodeLoader(Protocol):
    def load_node(self, label: str) -> BuildNode | None: ...
    def load_graph(self, root_label: str) -> dict[str, BuildNode]: ...
    def get_node_prompt(self, node_label: str) -> str | None: ...
```

A data class Protocol that bundles static node metadata with the `ToolProvider` interface. `deps` holds the node's dependency node labels, including its feedback deps; `feedback_deps` holds the labels that can receive feedback from the node (a subset of `deps`); `silent_deps` holds dependencies whose output is not readable. `src` is the node's declared source file (the artifact its agent writes; empty when the node declares none); `template` is the declared source file's template — its content initializes `src` at run start when `src` does not exist on disk (`None` when none is declared); `guide` is the node's declared guide — the guide node label, declared separately from `deps`, whose file the run's sandbox reads and treats per the step-mode flag (`None` when none is declared); `silent_srcs` holds the node's silent source files. Internal state fields (e.g., `_dependency_nodes`, `_agent_loop`) are implementation-specific and defined in the implementation spec. A loaded node resolves tool definitions and tool execution from the tool providers declared in its manifest; a tool call that no declared provider handles signals a tool failure.

**HLS Justification:** "Designates a runtime representation of a Bazel node."

## Term definitions

- **manifest** → term definition: a build-time file produced for a node, containing the node's label, prompt, declared tools, declared dependencies, silent dependencies, feedback deps, the declared source file, the silent source files, the declared source file's template (when configured), the guide (when the node declares one, declared separately from its dependencies), and an optional verification command; the exact file format is unspecified
- **loaded node** → the `BuildNode` type (definition in Data Types)
- **node prompt** → the `BuildNode.prompt` field (definition in Data Types)
- **dependency node** → the `BuildNode.deps` field (definition in Data Types)
- **tool provider** → the `ToolProvider` type from tool_provider (definition in Data Types)
- **feedback deps** → the `BuildNode.feedback_deps` field (definition in Data Types)
- **tool definition** → the `ToolDefinition` alias from tool_provider
- **tool result** → the `ToolResult` type from tool_provider
- **signal** → the `Signal` alias from tool_provider
- **tool failure** → the `ToolFailure` type from tool_provider
- **template** → term definition from sandbox
- **guide** → term definition from sandbox

## Component-Provided Operations

### `load_node`

```python
def load_node(self, label: str) -> BuildNode | None
```

**Purpose:** Load a single node from its manifest.

**Preconditions:** The node's manifest is valid JSON with all required fields; the manifest is accessible; the tool-provider modules the node declares are importable (per the interface's assumptions).

**Postconditions:** Returns a `BuildNode` with manifest data and tool-provider capability, or `None` if not found.

**Failure Handling:** Returns `None` for unknown labels.

**HLS Justification:** "The client may load a node by label."

### `load_graph`

```python
def load_graph(self, root_label: str) -> dict[str, BuildNode]
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

**Preconditions:** None.

**Postconditions:** Returns the node's prompt or `None` if not found.

**Failure Handling:** Returns `None` for unknown labels.

**HLS Justification:** "The client may query a node's prompt."


## Invariants

- Repeated loads of the same label provide the same node.
- A node is loaded from its manifest when requested; a node's manifest is read when the node is first loaded.
- Manifests are never modified; loading reads them only.
- Manifest file paths are derived deterministically from labels.


## Non-Concerns

- **Cache eviction policy:** Whether and when the cache evicts entries is unspecified.
- **Manifest resolution algorithm:** The exact mechanism for resolving a label to a manifest file (e.g., `//pkg:target` → `pkg/target_manifest.json` or the `RUNFILES_DIR` environment variable) is unspecified.

