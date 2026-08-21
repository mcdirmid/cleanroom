# bazel_node_loader_impl

fulfills: bazel_node_loader
imports: tool_provider (tool definitions and execution), agent_loop (prompt running)
terms (from bazel_node_loader): manifest, loaded node, node prompt, dependency node, tool provider, feedback deps
terms (from tool_provider): tool definition, tool result, signal, tool failure
terms (from agent_loop): run

## Deltas

- Constructs loaded nodes from manifests and caches them by label.
- Single-node loading: resolve a manifest from the label's derived filesystem path, construct the loaded node with the manifest's data (tool providers are resolved lazily at runtime), and cache it by label on success.
- Graph loading: load the root loaded node and recursively load its transitive dependencies.
- A loaded node's deps include its feedback deps: when a manifest's feedback deps are not already among its deps, they are added to the loaded node's deps.
- Prompt queries provide the loaded node's prompt if loaded.
- Each loaded node resolves tool definitions and tool execution from the tool providers declared in its manifest; a tool call is answered by the first declared provider that handles it, and a tool call no declared provider handles signals a tool failure.
- A loaded node runs prompts by delegating to an agent loop configured on the node.
- [boundary] A node is cached only after successful construction; partial loads do not populate the cache.
- [boundary] Invalid labels and missing manifests do not populate the cache.
- [ordering] Dependencies are resolved via the loader before dependent nodes are fully usable.
- [state] Tool providers are loaded dynamically at runtime.
- [external] Tool provider modules resolved via importlib; an externally configured agent loop.
- [failure] A manifest that cannot be found does not populate the cache.

## Non-concerns

- Tool-provider loading failures: the behavior when a declared tool provider module cannot be imported is unspecified.
