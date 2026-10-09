<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:00:00Z
CHANGE: new file
CODE_HASH: 0c01a8dc219b
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# uv_target interface component

imports: dag_storage, file_paths

## Intent

Multi-step workflows require deterministic node addressing and durable state storage within project package structures. Target specifications arrive from command-line arguments, dependency manifests, and directory layouts in various string forms. The uv_target interface component defines operations to convert arbitrary target identifier strings into canonical node references in graph storage and resolve the workspace package directories that contain them.

By normalizing target strings and deriving package directories, the component ensures consistent node identity and physical location resolution across the build graph.

## Factored Contracts

### Typing

- A node directory is a workspace path addressing the workspace package directory of a node.

### Contracts

- A caller supplies a target identifier string when normalizing a target. [normalize_target_identifier_supplied]
- A caller supplies a node when extracting a node directory. [extract_node_dir_node_supplied]
- The uv target normalizes an arbitrary target identifier string into a canonical node. [normalize_identifier_to_node]
- The uv target extracts a node directory from a node. [extract_node_dir_from_node]

### Woven Contracts

- Normalizing target identifiers converts arbitrary string representations into canonical dag nodes. [normalize_target_identifier_supplied, normalize_identifier_to_node, dag_storage: [access_dag_dependencies]]
- Extracting a node directory derives the package workspace path corresponding to a node. [extract_node_dir_node_supplied, extract_node_dir_from_node, file_paths: [create_ws_path]]

## Grounding

### Knowledge Provisions

- Target normalization and node package directory extraction service. [uv_target_service]

### Knowledge Requirements

- Parsing and normalization of arbitrary target label formats into canonical nodes.
  - Deferred: Delegated to uv_target_labels_ext in implementation.
- Translation of canonical package identifiers into workspace-relative paths.
  - Deferred: Delegated to uv_target_labels_ext and file_paths in implementation.
