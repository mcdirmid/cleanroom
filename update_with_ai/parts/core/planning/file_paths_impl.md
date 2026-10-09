<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: d42f67f1b9b0
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# file_paths_impl implementation component

imports: filesystem_ext
implements: file_paths

## Intent

Manipulating filesystem paths directly without boundary validation risks format inconsistencies and cross-platform path separator mismatches. The file_paths_impl implementation component enforces strict path boundaries by consulting the host filesystem to validate absolute paths, verifying relative workspace paths, and joining relative paths against workspace roots.

By centralizing normalization routines and relying on host filesystem mechanics, the implementation ensures all generated path records contain platform-canonical representations free from redundant separators and parent directory traversal segments.

## Factored Contracts

### Contracts

- The file path manager rejects empty path strings. [reject_empty_path_strings]
- Rejecting empty path strings fails indicating that a path cannot be empty. [fail_path_cannot_be_empty]
- The file path manager validates path representations using the host filesystem. [validate_with_host_fs]
- The file path manager resolves path representations using the host filesystem. [resolve_with_host_fs]
- Validating paths normalizes redundant separators into encapsulated path records. [normalize_redundant_separators]
- Validating paths resolves relative directory segments into encapsulated path records. [resolve_relative_directory_segments]
- Absolute path creation normalizes path representations into encapsulated records. [normalize_abs_path]
- Workspace path creation normalizes relative path representations into encapsulated records. [normalize_ws_path]
- Path resolution joins the relative workspace path to the workspace root absolute path using the host filesystem. [join_paths_with_host_fs]
- Path resolution produces a normalized absolute path record. [produce_normalized_resolved_path]

### Woven Contracts

- When given an empty path string, the file path manager rejects the path with a failure indicating that a path cannot be empty. [reject_empty_path_strings, fail_path_cannot_be_empty, file_paths: [raise_validation_error]]
- When creating an absolute path, the file path manager validates against the host filesystem, normalizes redundant separators and relative segments, and produces a normalized absolute path record. [validate_with_host_fs, normalize_redundant_separators, resolve_relative_directory_segments, normalize_abs_path, file_paths: [create_abs_path, reject_relative_absolute]]
- When creating a workspace path, the file path manager validates against the host filesystem, normalizes redundant separators and relative segments, and produces a normalized workspace path record. [validate_with_host_fs, normalize_redundant_separators, resolve_relative_directory_segments, normalize_ws_path, file_paths: [create_ws_path, reject_absolute_workspace, reject_leading_separators]]
- When resolving a workspace path against a workspace root absolute path, paths are joined using the host filesystem into a normalized absolute path record. [resolve_with_host_fs, join_paths_with_host_fs, produce_normalized_resolved_path, file_paths: [resolve_ws_path, combine_root_and_ws_path]]

## Grounding

### Knowledge Provisions

- Strongly-typed path construction and validation for host, workspace, and absolute paths. [typed_path_construction]
- Path resolution anchoring relative workspace paths to workspace roots. [path_resolution_service]

### Inherited Deferred Requirements

- Path string syntactic validation and separator normalization.
  - Grounded: [filesystem_ext: [host_path_operations]]
- Combining root and relative paths into normalized absolute paths.
  - Grounded: [filesystem_ext: [host_path_operations]]

### Knowledge Requirements

- Empty path detection and diagnostic error raising.
  - Grounded: [caller input]
