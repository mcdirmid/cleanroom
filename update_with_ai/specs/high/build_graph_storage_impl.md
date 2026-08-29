# build_graph_storage_impl

fulfills: build_graph_storage
imports: dag_storage (contract), build_message_store (package message data), manifest_node_loader (manifest resolution)
terms (from dag_storage): node, message, message kind, pending message, dependency, propagating dependency, reverse dependency
terms (from build_graph_storage): node definition, package directory, silent dependency, star dependency
terms (from build_message_store): package message data, textproto format
terms (from manifest_node_loader): manifest resolution, synthetic definition
terms (refined): node

## Deltas

- Coordinates storage queries and DAG navigation by delegating message persistence to build_message_store and workspace definition resolution to manifest_node_loader.
- Resolves node labels to package directories, node definitions, and dependency edges from the loaded graph data.
- Resolving a node's dependencies records the node as a known reverse dependency of each propagating dependency it provides via build_message_store.
- [state] Resolved lookups are served from data built when the component is initialized; cached values are never stale relative to the configured graph source.
- [refines] node -> a Bazel target identified by its label.

## Non-concerns

- Direct manifest parsing: delegated to manifest_node_loader.
- Textproto serialization: delegated to build_message_store.
