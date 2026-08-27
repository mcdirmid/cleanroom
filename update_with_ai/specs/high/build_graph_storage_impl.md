# build_graph_storage_impl

fulfills: build_graph_storage
imports: dag_storage (contract), sandbox (configuration construction)
terms (from dag_storage): node, message, message kind, pending message, dependency, propagating dependency, reverse dependency
terms (from build_graph_storage): node definition, package directory, silent dependency, star dependency
terms (from run_control): blame, blame target
terms (from file_view): template, virtual name
terms (from build_node_loader): manifest, feedback deps
terms (refined): node

## Deltas

- Resolves node labels to package directories, node definitions, and dependency edges from the configured graph source.
- Never invokes Bazel tooling during processing: bazel query, cquery, and aspects are at most offline extraction tools used outside the component's processing.
- A dependency declared by a node that lacks a manifest of its own is given a manifest derived from its label, so every declared dependency resolves to a node.
- Messages persist in a single file per Bazel package directory (the directory containing the node's BUILD file), named `.update_with_ai.textproto`.
- All nodes whose targets are defined in the same package share that package's message file, with messages and known reverse dependencies indexed by node within the file.
- The message kind is persisted with each stored message.
- The message file's content is the `update_with_ai` message (the message type defined by the `update_with_ai.proto` schema) in the protobuf text format.
- Resolving a node's dependencies records the node as a known reverse dependency of each propagating dependency it provides: each propagating dependency's entry in the message file gains the node among its known reverse dependencies. A node's propagating dependencies are its declared deps (including its feedback deps); silent deps are dependencies (cleaned before the node) but are not recorded, so a silent dep's changes do not propagate to the node.
- The sandbox configuration constructed for a node grants read access to the node's declared source, its own silent sources (so the agent can read and edit them), and its deps' declared sources, and write access to the node's own declared source and silent sources. Deps' silent sources are not readable, and silent deps' declared sources are not readable.
- The sandbox configuration constructed for a node includes the template content for the node's declared source file, when the node declares a template.
- A node's deps include its feedback deps: feedback deps' declared sources are readable, exactly as deps' declared sources are.
- A node's deps include its star deps: the sandbox configuration constructed for a node grants read access to the declared source of each star dep and of every node in its transitive closure over star dependencies (never through non-star dependencies or silent dependencies). The closure is computed at initialization from the loaded manifests; a star dep's own star deps are followed, never its deps or silent deps.
- The blame targets in the sandbox configuration map each feedback dep's declared source (by its virtual name) to the feedback dep's node; only feedback deps may receive feedback from the node.
- [ordering] Messages are appended to a node's pending set in the order delivered.
- Clearing a node's pending messages preserves the node's entry (its known reverse dependencies remain); deleting a node's data removes the node's entry entirely.
- [state] The message file is the state; the component maintains no in-memory state.
- [state] Resolved lookups are served from data built when the component is initialized; cached values are never stale relative to the configured graph source.
- [external] The configured graph source (workspace files or a precomputed graph) and the filesystem.
- [external] The `update_with_ai.proto` schema (the message type the package message file encodes).
- [failure] A storage operation that fails before completing does not update the messages (previously stored messages are preserved).
- [failure] Unknown labels raise an error for all queries (a precondition violation; no exception is required).
- [refines] node -> a Bazel target identified by its label.

## Non-concerns

- Concurrency: behavior with concurrent writers is unspecified.
- Label canonicalization: normalization of label spellings is unspecified.
