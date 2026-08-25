<!-- Dependencies (md files to read alongside this one):
  - tool_provider-low.md
  - sandbox-low.md
-->

# Interface LLS: bazel_node_loader

## Data Types
```python
from typing import Protocol, TypeAlias

from tool_provider import ToolDefinition, ToolResult, ToolFailure, ExecutionSignal, TerminationResult, ToolCall
from sandbox import FileContent

NodeLabel: TypeAlias = str
NodePrompt: TypeAlias = str
FilePath: TypeAlias = str
ToolProviderLabel: TypeAlias = str

from dataclasses import dataclass

@dataclass
class NodeManifest:
    label: NodeLabel
    prompt: str
    tools: list[ToolDefinition]
    dependencies: list[NodeLabel]
    silent_dependencies: list[NodeLabel]
    feedback_deps: list[NodeLabel]
    source_file: FilePath
    silent_source_files: list[FilePath]
    template: FileContent | None
    guide: FileContent | None
    verification_command: str | None

class LoadedNode(Protocol):
    def get_tool_definitions(self) -> list[ToolDefinition]: ...
    def execute_tool_call(self, tool_call: ToolCall) -> tuple[list[ToolResult] | None, ExecutionSignal, TerminationResult | ToolFailure | None]: ...
    def get_dependencies(self) -> list[NodeLabel]: ...
    def get_feedback_deps(self) -> list[NodeLabel]: ...
    def get_prompt(self) -> NodePrompt: ...
    def get_source_file(self) -> FilePath: ...

class BazelNodeLoader(Protocol):
    def load_node(self, label: NodeLabel) -> LoadedNode | None: ...
    def load_graph(self, root_label: NodeLabel) -> dict[NodeLabel, LoadedNode]: ...
    def get_prompt(self, label: NodeLabel) -> NodePrompt | None: ...
```

**NodeLabel:** A string identifying a Bazel target (node).

**NodePrompt:** The agent prompt string associated with a loaded node.

**FilePath:** The full filesystem path to a source file.

**ToolProviderLabel:** A Bazel label identifying a tool provider module.

**NodeManifest:** A build-time file produced for a node, containing the node's label, prompt, declared tools, declared dependencies, silent dependencies, feedback deps, the declared source file, the silent source files, the declared source file's template (when configured), the guide (when the node declares one, declared separately from its dependencies), and an optional verification command.

**LoadedNode:** A runtime representation of a Bazel target — its manifest data (label, prompt, tools, dependencies, the declared source file, its template, the silent source files, the guide) — providing tool definitions and tool execution resolved at runtime from its declared tools. Tool calls are executed through the `ToolCall` type from `tool_provider`.

## Term definitions

- **manifest** → the `NodeManifest` type
- **loaded node** → the `LoadedNode` protocol
- **node prompt** → the `NodePrompt` alias
- **dependency node** → term definition: a `LoadedNode` resolved from a manifest, representing a declared dependency of this node
- **feedback deps** → term definition: dependency node targets that can receive feedback from the node; feedback deps are also declared dependencies of the node
- **tool provider** → term definition: a component identified by a `ToolProviderLabel` that provides tool definitions and executes tool calls
- **silent dependencies** → term definition: dependencies of a node that are not exposed as visible dependency nodes but may be loaded internally
- **graph** → term definition: the transitive closure of nodes reachable from a root label through declared dependencies and silent dependencies
- **tool definition** → the `ToolDefinition` alias from tool_provider
- **tool result** → the `ToolResult` alias from tool_provider
- **signal** → the `ExecutionSignal` alias from tool_provider
- **tool failure** → the `ToolFailure` alias from tool_provider
- **template** → the `template` term from sandbox
- **guide** → the `guide` term from sandbox

## Component-Provided Operations

### `load_node`

```python
def load_node(self, label: NodeLabel) -> LoadedNode | None: ...
```

**Purpose:** Load a single node given its label. Reads the node's manifest and constructs a `LoadedNode` with its tool definitions, dependencies, and source files.

**Preconditions:** The manifest file for the label is accessible (when it exists).

**Postconditions:** Returns a `LoadedNode` with the node's manifest data, tool definitions resolved from declared tools, and source files. When the manifest cannot be found, returns `None`.

**Failure Handling:** Returns `None` when the manifest cannot be found. No exception is raised for missing manifests.

**HLS Justification:** Contract → Operations → "Load a single node given its label"; Contract → Guarantees → "A loaded node is provided when its manifest is found; when the manifest cannot be found, no node is provided."

### `load_graph`

```python
def load_graph(self, root_label: NodeLabel) -> dict[NodeLabel, LoadedNode]: ...
```

**Purpose:** Load an entire graph starting from a root label, obtaining a mapping of all reachable node labels to their nodes.

**Preconditions:** The manifest file for the root label is accessible (when it exists).

**Postconditions:** Returns a `dict[NodeLabel, LoadedNode]` mapping every reachable node label (including the root and all transitive dependencies) to its `LoadedNode`.

**Failure Handling:** Returns an empty dict when the root manifest cannot be found.

**HLS Justification:** Contract → Operations → "Load an entire graph starting from a root label, obtaining a mapping of all reachable node labels to their nodes"; Contract → Guarantees → "The graph is loaded starting from the root label, recursively loading all transitive dependencies, including silent dependencies"; Contract → Guarantees → "A node's deps include its feedback deps; loading a node's dependencies loads its feedback deps as dependency nodes"; Contract → Guarantees → "Repeated loads of the same label provide the same node."

### `get_prompt`

```python
def get_prompt(self, label: NodeLabel) -> NodePrompt | None: ...
```

**Purpose:** Retrieve a node's prompt without loading the full node. Reads only the manifest to extract the prompt.

**Preconditions:** The manifest file for the label is accessible (when it exists).

**Postconditions:** Returns the node's prompt when the manifest is found; returns `None` when the manifest cannot be found.

**Failure Handling:** Returns `None` when the manifest cannot be found.

**HLS Justification:** Contract → Operations → "Retrieve a node's prompt without loading the full node."

## Invariants

- Manifest file paths are derived deterministically from labels.
- A loaded node is provided when its manifest is found; when the manifest cannot be found, no node is provided (manifests are never modified).
- Repeated loads of the same label provide the same node.
- A node is loaded from its manifest when requested.
- A node's deps include its feedback deps; loading a node's dependencies loads its feedback deps as dependency nodes.
- Tool definitions are resolved from the node's declared tools; a tool call with no tool handles signals a tool failure.
- Dependency nodes are resolved from the node's declared dependencies.
- The graph is loaded starting from the root label, recursively loading all transitive dependencies, including silent dependencies.

## Non-Concerns

- **Cache eviction policy:** whether and when the cache evicts entries is unspecified — the HLS states this as a non-concern.
- **Manifest file format:** the exact file format is unspecified; manifests are assumed to be valid JSON containing all required fields — the HLS states this as an assumption.
- **Manifest path derivation:** the exact algorithm for deriving manifest file paths from labels is unspecified, only that it is deterministic — the HLS states this as a guarantee that paths are deterministic but not the algorithm.
- **Tool provider module loading:** the specific mechanism for importing tool provider modules is unspecified; modules are assumed to be importable — the HLS states this as an assumption.
- **Manifest validation details:** the exact validation rules for manifest fields are unspecified; manifests are assumed to contain all required fields — the HLS states this as an assumption.
