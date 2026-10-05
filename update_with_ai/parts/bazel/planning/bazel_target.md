<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-05T05:31:13Z
CHANGE: Remove code-level constructor constraint from typing
CODE_HASH: 7a65d6d14ebf
-->

# bazel_target interface component

imports: dag_storage, file_paths

## Intent

Multi-step workflows require deterministic node addressing and durable state storage within project package structures. The bazel_target interface component defines operations to convert arbitrary Bazel target identifier strings into canonical node references in dag storage and resolve the workspace package directories that contain them.

By normalizing target strings and deriving package directories, the component ensures consistent node identity and physical location resolution across the build graph.

## Factored Contracts

### Typing

- A node directory is a workspace path addressing the workspace package directory of a node.

### Contracts

- A caller supplies a target identifier string when normalizing a target. [normalize_target_identifier_supplied]
- A caller supplies a node when extracting a node directory. [extract_node_dir_node_supplied]
- The bazel target normalizes an arbitrary Bazel target identifier string into a canonical node. [normalize_identifier_to_node]
- The bazel target extracts a node directory from a node. [extract_node_dir_from_node]

## Woven Contracts

- Normalizing target identifiers converts arbitrary string representations into canonical dag nodes. \[normalize_target_identifier_supplied, normalize_identifier_to_node, dag_storage: [access_dag_dependencies]\]
- Extracting a node directory derives the package workspace path corresponding to a node. \[extract_node_dir_node_supplied, extract_node_dir_from_node, file_paths: [create_ws_path]\]
