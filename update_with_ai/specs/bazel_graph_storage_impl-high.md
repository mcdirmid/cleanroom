# bazel_graph_storage_impl

fulfills: bazel_graph_storage
imports: dag_storage (contract), sandbox (configuration construction)
terms (from dag_storage): node, message, pending message, dependency, propagating dependency, reverse dependency
terms (from bazel_graph_storage): node definition, package directory, silent dependency
terms (from sandbox): blame, blame target
terms (from bazel_node_loader): manifest, feedback deps
terms (refined): node -> a Bazel target identified by its label

## Deltas beyond the bazel_graph_storage contract

### Behavior

- Resolves node labels to package directories, node definitions, and dependency edges from the configured graph source.
- Never invokes Bazel tooling during processing: bazel query, cquery, and aspects are at most offline extraction tools used outside the component's processing.
- A dependency declared by a node that lacks a manifest of its own is given a manifest derived from its label, so every declared dependency resolves to a node.
- Messages persist in a single file per Bazel package directory (the directory containing the node's BUILD file); all nodes whose targets are defined in the same package share that package's message file, with messages and known reverse dependencies indexed by node within the file.
- Resolving a node's dependencies records the node as a known reverse dependency of each propagating dependency it provides, per the dag_storage contract: each propagating dependency's entry in the message file gains the node among its known reverse dependencies. A node's propagating dependencies are its declared deps (including its feedback deps); silent deps are dependencies (cleaned before the node) but are not recorded, so a silent dep's changes do not propagate to the node.
- The sandbox configuration constructed for a node grants read access to the node's declared sources and its deps' declared sources, and write access to the node's own declared sources (including its silent sources). Silent deps' declared sources are not readable.
- A node's deps include its feedback deps: feedback deps' declared sources are readable, exactly as deps' declared sources are.
- The blame targets in the sandbox configuration are the node's feedback deps; only feedback deps may receive feedback from the node.

### Operation Boundaries

- Storage operations are atomic per node, per the dag_storage contract.
- Queries are read-only and do not modify the workspace, per the bazel_graph_storage contract.

### Ordering

- Messages are appended to a node's pending set in the order delivered.

### State Management

- The message file is the state; the component maintains no in-memory state.
- Resolved lookups are served from data built when the component is initialized; cached values are never stale relative to the configured graph source.

### External Dependencies

- The configured graph source (workspace files or a precomputed graph) and the filesystem.

### Error Handling

- Per the dag_storage contract, storage failures are assumed not to occur; if they do, behavior is undefined.
- A storage operation that fails before completing does not update the messages (previously stored messages are preserved).
- Unknown labels raise an error for all queries (a precondition violation; no exception is required).
- Graph-source failures signal failure without side effects.

### Refined terms

- node -> a Bazel target identified by its label, per the bazel_graph_storage refinement.

## Non-concerns

- Concurrency: behavior with concurrent writers is unspecified.
- Label canonicalization: normalization of label spellings is unspecified.
