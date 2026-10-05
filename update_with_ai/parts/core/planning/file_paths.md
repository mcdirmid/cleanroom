<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T02:07:35Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: ce6a181dd3cc
-->

# file_paths interface component

## Intent

Manipulating filesystem locations as untyped strings allows invalid path formats, relative paths masquerading as absolute paths, and accidental leaks between host paths and relative workspace paths. The file_paths interface component establishes strongly-typed representations for host paths, absolute paths, and workspace paths, providing a system service to create, validate, and resolve them.

By encapsulating string representations within dedicated path types and centralizing path construction within a file path manager, the architecture eliminates directory traversal risks and ensures workspace paths remain strictly relative to a workspace root without leading path separators.

## Factored Contracts

### Typing

- A host path encapsulates a path string on the host filesystem.
- An absolute path is a host path representing an absolute filesystem path.
- A workspace path is a host path representing a relative filesystem path anchored to a workspace root without leading path separators.
- A workspace root is an absolute path representing the root directory of a workspace.
- A path validation error indicates that a path string is invalid for the target path type.

### Contracts

- A caller supplies a non-empty path string when requesting path creation. [create_path_input_supplied]
- A caller supplies a workspace path when requesting path resolution. [resolve_ws_path_supplied]
- A caller supplies a workspace root absolute path when requesting path resolution. [resolve_root_supplied]
- A system's file path manager creates host paths from path strings. [create_host_path]
- A system's file path manager creates workspace paths from path strings. [create_ws_path]
- A system's file path manager creates absolute paths from path strings. [create_abs_path]
- A system's file path manager validates path strings based on target path type. [validate_path_strings]
- A system's file path manager resolves workspace paths into absolute paths using a workspace root absolute path. [resolve_ws_path]
- Path validation rejects path strings with leading path separators when creating workspace paths. [reject_leading_separators]
- Path validation rejects non-absolute path strings when creating absolute paths. [reject_relative_absolute]
- Path validation rejects absolute path strings when creating workspace paths. [reject_absolute_workspace]
- Path validation raises a path validation error on invalid path strings. [raise_validation_error]
- Path resolution combines the workspace root absolute path with the workspace path to produce an absolute path. [combine_root_and_ws_path]

## Woven Contracts

- Under non-empty input strings, a file path manager creates valid host paths, workspace paths, and absolute paths. [create_path_input_supplied, create_host_path, create_ws_path, create_abs_path, validate_path_strings]
- When creating a workspace path from a path string with leading separators, path validation fails raising a path validation error. [create_path_input_supplied, validate_path_strings, reject_leading_separators, raise_validation_error]
- When creating a workspace path from an absolute path string, path validation fails raising a path validation error. [create_path_input_supplied, validate_path_strings, reject_absolute_workspace, raise_validation_error]
- When creating an absolute path from a relative path string, path validation fails raising a path validation error. [create_path_input_supplied, validate_path_strings, reject_relative_absolute, raise_validation_error]
- When resolving a workspace path against a workspace root absolute path, the file path manager produces the combined absolute path. [resolve_ws_path_supplied, resolve_root_supplied, resolve_ws_path, combine_root_and_ws_path]
