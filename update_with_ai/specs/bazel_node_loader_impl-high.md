# bazel_node_loader_impl

fulfills: bazel_node_loader
imports: tool_provider (tool definitions and execution), agent_loop (prompt running)
terms (from bazel_node_loader): manifest, loaded node, node prompt, dependency node, tool provider
terms (from tool_provider): tool definition, tool result, signal, tool failure
terms (from agent_loop): run

## Deltas beyond the bazel_node_loader contract

### Behavior

- Constructs loaded nodes from manifests and caches them by label.
- Single-node loading: resolve a manifest from the label's derived filesystem path, construct the loaded node with the manifest's data (tool providers are resolved lazily at runtime), and cache it by label on success.
- Graph loading: load the root loaded node and recursively load its transitive dependencies.
- Prompt queries provide the loaded node's prompt if loaded.
- Each loaded node resolves tool definitions and tool execution from the tool providers declared in its manifest; a tool call is answered by the first declared provider that handles it, and a tool call no declared provider handles signals a tool failure.
- A loaded node runs prompts by delegating to an agent loop configured on the node.

### Operation Boundaries

- A node is cached only after successful construction; partial loads do not populate the cache.
- Invalid labels and missing manifests do not populate the cache.

### Ordering

- Dependencies are resolved via the loader before dependent nodes are fully usable.

### State Management

- Nodes are cached by label per the bazel_node_loader contract.
- Tool providers are loaded dynamically at runtime.

### External Dependencies

- Tool provider modules resolved via importlib; an externally configured agent loop.

### Error Handling

- A manifest that cannot be found does not populate the cache.
