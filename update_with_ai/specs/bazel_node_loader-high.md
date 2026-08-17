# bazel_node_loader

imports: tool_provider (tool definitions and execution)
terms (from tool_provider): tool definition, tool result, signal, tool failure
terms (owned): manifest, loaded node, node prompt, dependency node, tool provider

## Purpose

Provides runtime loading of node manifests (produced at build time by update_with_ai) into working loaded nodes with tool providers, dependencies, and agent loops.

## Owned definitions

- Manifest: a build-time file produced for a node, containing the node's label, prompt, declared tools, declared and silent dependencies, declared and silent source files, and an optional verification command. The exact file format is unspecified.
- Loaded node: a runtime representation of a Bazel target — its manifest data (label, prompt, tools, dependencies, source files) — providing tool definitions and tool execution resolved at runtime from its declared tools.
- Node prompt: the agent prompt string associated with a loaded node.
- Dependency node: a loaded node resolved from a manifest, representing a declared dependency of this node.
- Tool provider: a component that provides tool definitions and executes tool calls, identified by a Bazel label.

## Observable dataflow

- Inputs: a root label to start graph loading, a single node label to load, or a node label for a prompt query.
- Outputs: a loaded node; a mapping of all reachable labels to loaded nodes; a node's prompt.
- Nodes load lazily from manifests at filesystem locations derived from their labels, resolved relative to a configured runfiles directory.
- Nodes are cached by label; repeated loads of the same label provide the same node.
- Graph loading starts from the root label and recursively loads all transitive dependencies, including silent dependencies.

## Contract

**The client provides:**

- A root label to start graph loading, or a single node label to load.
- A node label to query for its prompt.

**The client may:**

- Load a single node given its label.
- Load an entire graph starting from a root label, obtaining a mapping of all reachable node labels to their nodes.
- Retrieve a node's prompt without loading the full node.
- Through a loaded node: resolve tool definitions, execute a tool call, and load the node's dependencies by their labels.

**The component guarantees:**

- A loaded node is provided when its manifest is found; when the manifest cannot be found, no node is provided (manifests are never modified).
- Nodes are cached by label; repeated loads of the same label provide the same node.
- The graph is loaded starting from the root label, recursively loading all transitive dependencies, including silent dependencies.
- Manifest file paths are derived deterministically from labels.
- Tool definitions are resolved from the node's declared tools; a tool call no tool handles signals a tool failure.
- Dependency nodes are resolved from the node's declared dependencies.

**The component assumes:**

- Manifest files are valid JSON and contain all required fields.
- Manifest files are accessible from the configured runfiles path.
- Tool provider modules are importable from the configured runfiles path.

## Non-concerns

- Cache eviction policy: whether and when the cache evicts entries is unspecified.
