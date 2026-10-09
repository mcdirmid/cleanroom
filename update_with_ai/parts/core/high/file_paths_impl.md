<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-05T04:42:50Z
CHANGE: Add delegated collaborator and refine validation and normalization behavior
CODE_HASH: 5fa8c593ef32
-->

# file_paths_impl implementation component

imports: filesystem_ext
implements: file_paths

## Purpose

The file_paths_impl implementation component realizes path validation and resolution services using host filesystem operations and path normalization.

Manipulating filesystem paths directly without boundary validation risks format inconsistencies and cross-platform path separator mismatches. The file_paths_impl implementation component enforces strict path boundaries by consulting the host filesystem to validate absolute paths, verifying relative workspace paths, and joining relative paths against workspace roots.

**Out of scope:** The file_paths_impl implementation component does not create file aliases, read file contents, or execute filesystem mutations; these are handled by other components.

**Delegated:** Native path inspection and host filesystem checks are delegated to filesystem_ext.

## Types and Behavior

The file path manager rejects empty path strings with a failure indicating that a path cannot be empty.

When validating an absolute path, the file path manager checks that the path is absolute according to the host filesystem, failing with an error if given a relative path. When validating a workspace path, it checks that the path is relative without leading separators, failing with an error if given an absolute path.

Validating paths normalizes redundant separators and resolves relative directory segments into encapsulated path records. Resolving a workspace path against the absolute path of a workspace root joins the relative path string to the root and normalizes the resulting path into an absolute path record.
