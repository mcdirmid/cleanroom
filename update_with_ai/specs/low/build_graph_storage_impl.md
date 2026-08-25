<!-- Dependencies (md files to read alongside this one):
  - build_graph_storage.md
  - dag_storage.md
  - sandbox.md
  - build_node_loader.md
-->

# Implementation LLS: build_graph_storage_impl

## Data Types
```python
from build_graph_storage import (
    BuildGraphStorage,
    NodeDefinition,
    PackageDirectory,
    GraphConfig,
)
from dag_storage import NodeMessage, PendingMessages, NodeDependencies, KnownReverseDependencies
from sandbox import SandboxConfig

class BaseBuildGraphStorageImpl(BuildGraphStorage):
    def __init__(self, config: GraphConfig): ...

class BuildGraphStorageFileImpl(BaseBuildGraphStorageImpl): ...
```

Constructed with the `build_graph_storage` interface's `GraphConfig` (see Interface LLS Data Types); it bundles no imported capabilities. The interface contract guarantees that `GraphConfig` provides at least one of `graph_source` or `workspace_root`.

## Behavioral Description

`BaseBuildGraphStorageImpl` (abstract base class) implements the `BuildGraphStorage` Protocol by:

1. **`__init__`**: Resolves the graph source from config (specifying one of `graph_source` or `workspace_root`). Then calls abstract methods `_build_adjacency`, `_build_definitions`, and `_build_package_dirs`, implemented by subclasses.

2. **`resolve_node_definition`**: Returns a `NodeDefinition` (agent prompt + sandbox configuration) from the built-in definitions map.

3. **`resolve_package_directory`**: Derives the package directory (BUILD file's directory) from the built-in mapping.

4. **`get_node_dependencies`**: Returns the node's direct dependencies from the adjacency map. As a side effect (per the `dag_storage` contract), records the node as a known reverse dependency of each propagating dependency: each propagating dependency's message-file entry gains the node among its known reverse dependencies. Dependencies whose changes do not propagate to the node (silent deps) are dependencies for graph traversal but are not recorded.

5. **`get_known_reverse_dependencies`**: Returns the node's known reverse dependencies from its message-file entry (empty if the file or the node's entry is absent).

6. **`get_pending_messages`** — Returns the node's pending messages from the message file in the node's package directory (an empty list if the file or the node's entry is absent).

7. **`add_messages`** — Appends the given messages to the node's pending set in the message file and persists the result.

8. **`clear_pending_messages`** — Removes the node's pending messages from its entry in the message file while preserving its known reverse dependencies, and persists the result; a node with no entry is unchanged.

9. **`delete_node_data`** — Deletes the node's data: removes the node's entry from the file entirely, so both its pending messages and its known reverse dependencies are deleted.

Persistence: a single file named `.update_with_ai.textproto` per package directory, serialized from the `update_with_ai` message type defined by the `update_with_ai.proto` schema in the protobuf text format, mapping node IDs to entries holding the node's pending messages (each with its kind and text) and known reverse dependencies. Reads treat a missing file as empty. Writes are atomic: new content is written to a temporary file, which is then atomically replaced onto `.update_with_ai.textproto`. A write that fails before the replacement leaves the previous file unchanged (the node's data is not updated).

**Subclass: `BuildGraphStorageFileImpl`** (concrete implementation) overrides the abstract methods and loads all data from manifests during `__init__`:
- The subclass requires `workspace_root` in the config (a `graph_source`-only config is rejected): it locates manifest files under the workspace root.
- For each manifest file, constructs a `NodeDefinition` with `prompt` from the manifest and `sandbox_config` populated from `src`, `template`, `silent_srcs`, `deps`, `silent_deps`, `feedback_deps`, `guide`, and `verify` fields (see `_build_sandbox_config` helper).
- For each node, builds adjacency from `deps` and `silent_deps` plus the guide node when the manifest declares a guide (the guide node is a dependency of the node, cleaned before it). The deps used for readability and adjacency are the manifest's `deps` expanded with its `feedback_deps` and `star_deps` (deduplicated), so a node's deps always include its feedback deps and star deps even when the manifest was produced without the macro's own expansion.
- For each node, builds the propagating deps from its deps (the manifest's `deps` expanded with its `feedback_deps` and `star_deps`); silent deps are adjacency-only and are not propagating deps.
- For each node with `star_deps`, computes the star closure from the loaded manifests: every node reachable from a star dep through `star_deps` (never `deps` or `silent_deps`), traversed once each. Each node in the closure contributes its declared `src` to the node's readable set exactly like a direct dep; a star dep whose manifest is not loaded contributes nothing.
- A declared dependency without its own manifest is synthesized from its label (package directory derived from the label's package path; empty prompt, no declared source, no template, no dependencies), so that every declared dependency resolves to a node.
- Derives package directories from the manifest file location (mapped onto the real source tree via `BUILD_WORKSPACE_DIRECTORY` environment variable).

**`_build_sandbox_config` helper**: Given a manifest and file mappings, constructs a `SandboxConfig` with:
- `file_mappings`: the node's declared `src`, its `silent_srcs`, and the declared `src`s of its deps (and star-closure nodes), each mapped to its full filesystem path — a dependency's src maps into the dependency's package directory, the node's own src and silent srcs map into the node's package directory, and the guide file (when declared) maps into the guide's package directory; name collisions prefer the node's own files
- `readable_paths`: the node's own `src` plus its deps' `src`s and the `src` of every node in its star deps' transitive closure (deps include feedback deps and star deps; neither the node's own `silent_srcs` nor the deps' `silent_srcs` are readable, silent deps' `src`s are not readable, and star-closure traversal never follows `silent_deps`); the guide file when the manifest declares a guide
- `writable_paths`: the node's own `src` + `silent_srcs`
- `guide`: the guide's virtual name when the manifest declares a guide — the guide file is mapped (its path resolved relative to the real source tree) and listed in `readable_paths`, so the sandbox can read it and treat it per the step-mode flag; `None` when the manifest declares no guide
- `templates`: when the manifest declares a `template`, the node's declared `src` mapped to the template file's content — the template file's path is resolved relative to the real source tree (the `BUILD_WORKSPACE_DIRECTORY`-mapped root) and read at initialization; an empty mapping when the manifest declares no template
- `blame_targets`: the manifest's `feedback_deps` (only feedback deps may receive feedback from the node)
- `search_result_limit`: pinned to 10 — the maximum rendered matches a single search may return
- `verification_callback`: built from the manifest's `verify` field (a shell command string); `_build_verify_callback` runs the command via `subprocess` and returns `(success, output)` where `success` is `True` when the command exits 0. The success flag gates `advance` (see sandbox specs).

**HLS Justification:** Reads node manifests and constructs NodeDefinition objects from manifest fields.

## Invariants

- Storage operations are atomic per node
- Messages are appended to a node's pending set in the order delivered
- The message file is the sole state for messages and known reverse dependencies; the component maintains no in-memory state for them
- Resolved lookups (definitions, package directories, dependencies) are served from data built when the component is initialized; cached values are never stale relative to the configured graph source
- Unknown labels raise an error for all queries (a precondition violation; no exception is required)
- The implementation never invokes Bazel tooling (`bazel query`, `cquery`, aspects) during processing; those are at most offline extraction tools used outside the component

## Non-Concerns

- **Storage failures:** Filesystem errors are unexpected and unhandled by the implementation.
- **Harness file naming:** Pinned to `.update_with_ai.textproto` in the package directory (the interface leaves the filename open).
- **Concurrency:** Behavior with concurrent writers is unspecified.
- **Serialization format:** Messages (each with its kind and text) and known reverse dependencies are serialized in the protobuf text format per the `update_with_ai.proto` schema; the exact field layout is pinned by that schema.
- **Empty entries:** `delete_node_data` removes the node's key from the file rather than writing an empty entry; `clear_pending_messages` writes an entry with an empty message list when the node has known reverse dependencies, and removes the node's key when it has none.
- **Label canonicalization:** Normalization of label spellings is unspecified.


