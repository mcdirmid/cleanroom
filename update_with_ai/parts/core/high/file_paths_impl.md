# file_paths_impl implementation component

imports: filesystem_ext
implements: file_paths

## Purpose

The file_paths_impl implementation component realizes path validation and resolution services using host filesystem operations and path normalization.

Manipulating filesystem paths directly without boundary validation risks format inconsistencies and cross-platform path separator mismatches. The file_paths_impl implementation component enforces strict path boundaries by consulting the host filesystem to validate absolute paths, verifying relative workspace paths, and joining relative paths against workspace roots.

**Out of scope:** The file_paths_impl implementation component does not create file aliases, read file contents, or execute filesystem mutations; these are handled by other components.

## Types and Behavior

The file path manager validates and resolves path representations using the host filesystem.

Host paths encapsulate non-empty path strings. Absolute paths validate that path strings are absolute according to the host filesystem, raising a failure when relative, and normalize path representations into encapsulated records.

Workspace paths validate that path strings are relative without leading separators, raising a failure when absolute, and normalize relative path representations into encapsulated records.

Resolving a workspace path against the absolute path of a workspace root joins the relative workspace path to the root path using the host filesystem, producing a normalized absolute path record.
