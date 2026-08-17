<!-- Dependencies (md files to read alongside this one):
  - bazel_graph_storage-low.md
  - dag_storage-low.md
  - sandbox-low.md
  - bazel_node_loader-low.md
-->

# Implementation LLS: bazel_graph_storage_impl

## Data Types

```python
from dataclasses import dataclass
from bazel_graph_storage import (
    BazelGraphStorage,
    NodeDefinition,
    NodeId,
    PackageDirectory,
    GraphConfig,
)
from dag_storage import NodeMessage, PendingMessages, NodeDependencies, KnownReverseDependencies
from sandbox import SandboxConfig
```

```python
class BaseBazelGraphStorageImpl(BazelGraphStorage): ...
```

```python
class BazelGraphStorageFileImpl(BaseBazelGraphStorageImpl): ...
```

## Config

```python
Config = GraphConfig
```

The implementation is constructed with the `bazel_graph_storage` interface's `GraphConfig` (see Interface LLS Data Types). It bundles no imported capabilities. The interface contract guarantees that `GraphConfig` provides at least one of `graph_source` or `workspace_root`.

**HLS Justification:** Configured with a workspace root or graph source (per the `bazel_graph_storage` interface contract).

## Behavioral Description

`BaseBazelGraphStorageImpl` (abstract base class) implements the `BazelGraphStorage` Protocol by:

1. **`__init__`**: Resolves the graph source from config (specifying one of `graph_source` or `workspace_root`). Then calls abstract methods `_build_adjacency`, `_build_definitions`, and `_build_package_dirs`, implemented by subclasses.

2. **`resolve_node_definition`**: Returns a `NodeDefinition` (agent prompt + sandbox configuration) from the built-in definitions map.

3. **`resolve_package_directory`**: Derives the package directory (BUILD file's directory) from the built-in mapping.

4. **`get_node_dependencies`**: Returns the node's direct dependencies from the adjacency map. As a side effect (per the `dag_storage` contract), records the node as a known reverse dependency of each propagating dependency: each propagating dependency's message-file entry gains the node among its known reverse dependencies. Dependencies whose changes do not propagate to the node (silent deps) are dependencies for graph traversal but are not recorded.

5. **`get_known_reverse_dependencies`**: Returns the node's known reverse dependencies from its message-file entry (empty if the file or the node's entry is absent).

6. **`get_pending_messages`** — Returns the node's pending messages from the message file in the node's package directory (an empty list if the file or the node's entry is absent).

7. **`add_messages`** — Appends the given messages to the node's pending set in the message file and persists the result.

8. **`delete_node_data`** — Deletes the node's data: removes the node's entry from the file entirely, so both its pending messages and its known reverse dependencies are deleted.

Persistence: a single JSON file named `.update_with_ai.json` per package directory maps node IDs to entries holding the node's pending messages and known reverse dependencies. Reads treat a missing file as empty. Writes are atomic: new content is written to a temporary file, which is then atomically replaced onto `.update_with_ai.json`. A write that fails before the replacement leaves the previous file unchanged (the node's data is not updated).

**Subclass: `BazelGraphStorageFileImpl`** (concrete implementation) overrides the abstract methods and loads all data from manifests during `__init__`:
- The subclass requires `workspace_root` in the config (a `graph_source`-only config is rejected): it locates manifest files under the workspace root.
- For each manifest file, constructs a `NodeDefinition` with `prompt` from the manifest and `sandbox_config` populated from `srcs`, `silent_srcs`, `deps`, `silent_deps`, `feedback_deps`, and `verify` fields (see `_build_sandbox_config` helper).
- For each node, builds adjacency from `deps` and `silent_deps` (all declared dependencies are the node's direct dependencies). The deps used for readability and adjacency are the manifest's `deps` expanded with its `feedback_deps` (deduplicated), so a node's deps always include its feedback deps even when the manifest was produced without the macro's own expansion.
- For each node, builds the propagating deps from its deps (the manifest's `deps` expanded with its `feedback_deps`); silent deps are adjacency-only and are not propagating deps.
- A declared dependency without its own manifest is synthesized from its label (package directory derived from the label's package path; empty prompt, no sources, no dependencies), so that every declared dependency resolves to a node.
- Derives package directories from the manifest file location (mapped onto the real source tree via `BUILD_WORKSPACE_DIRECTORY` environment variable).

**`_build_sandbox_config` helper**: Given a manifest and file mappings, constructs a `SandboxConfig` with:
- `readable_paths`: the node's own `srcs` plus its deps' `srcs` (deps include feedback deps; neither the node's own `silent_srcs` nor the deps' `silent_srcs` are readable, and silent deps' `srcs` are not readable)
- `writable_paths`: the node's own `srcs` + `silent_srcs`
- `blame_targets`: the manifest's `feedback_deps` (only feedback deps may receive feedback from the node)
- `read_size_limit` and `search_result_limit`: values are not pinned in this spec (the implementation sets fixed values)
- `verification_callback`: built from the manifest's `verify` field (a shell command string).

**HLS Justification:** Reads node manifests and constructs NodeDefinition objects from manifest fields.

## Invariants

- Storage operations are atomic per node
- Messages and known reverse dependencies persist across component restarts (JSON file on disk)
- The message file is the sole state for messages and known reverse dependencies; the component maintains no in-memory state for them
- Resolved lookups (definitions, package directories, dependencies) are served from data built when the component is initialized; cached values are never stale relative to the configured graph source
- Queries are read-only; no workspace modification occurs (except during `__init__` of the subclass)
- Each query provides a consistent view of the graph
- Graph-source failures signal failure without side effects (the graph is unmodified)
- Storage failures are unexpected (filesystem errors) and unhandled by the implementation
- The implementation never invokes Bazel tooling (`bazel query`, `cquery`, aspects) during processing; those are at most offline extraction tools used outside the component

## Non-Concerns

- **Harness file naming:** Pinned to `.update_with_ai.json` in the package directory (the interface leaves the filename open).
- **Concurrency:** Behavior with concurrent writers is unspecified.
- **Serialization format:** Messages and known reverse dependencies are serialized as JSON; the node-ID-keyed mapping is an internal representation detail.
- **Empty entries:** `delete_node_data` removes the node's key from the file rather than writing an empty entry.
- **Label canonicalization:** Normalization of label spellings is unspecified.


