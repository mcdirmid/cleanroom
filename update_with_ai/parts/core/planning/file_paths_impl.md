# file_paths_impl implementation component

imports: filesystem_ext
implements: file_paths

## Intent

Manipulating filesystem paths directly without boundary validation risks format inconsistencies and cross-platform path separator mismatches. The file_paths_impl implementation component enforces strict path boundaries by consulting the host filesystem to validate absolute paths, verifying relative workspace paths, and joining relative paths against workspace roots.

By centralizing normalization routines and relying on host filesystem mechanics, the implementation ensures all generated path records contain platform-canonical representations free from redundant separators and parent directory traversal segments.

## Factored Contracts

### Contracts

- The file path manager validates path representations using the host filesystem. [validate_with_host_fs]
- The file path manager resolves path representations using the host filesystem. [resolve_with_host_fs]
- Absolute path creation normalizes path representations into encapsulated records. [normalize_abs_path]
- Workspace path creation normalizes relative path representations into encapsulated records. [normalize_ws_path]
- Path resolution joins the relative workspace path to the workspace root absolute path using the host filesystem. [join_paths_with_host_fs]
- Path resolution produces a normalized absolute path record. [produce_normalized_resolved_path]

## Woven Contracts

- When creating an absolute path, the file path manager validates against the host filesystem and produces a normalized absolute path record. [validate_with_host_fs, normalize_abs_path, file_paths: [create_abs_path, reject_relative_absolute]]
- When creating a workspace path, the file path manager validates against the host filesystem and produces a normalized workspace path record. [validate_with_host_fs, normalize_ws_path, file_paths: [create_ws_path, reject_absolute_workspace, reject_leading_separators]]
- When resolving a workspace path against a workspace root absolute path, paths are joined using the host filesystem into a normalized absolute path record. [resolve_with_host_fs, join_paths_with_host_fs, produce_normalized_resolved_path, file_paths: [resolve_ws_path, combine_root_and_ws_path]]
