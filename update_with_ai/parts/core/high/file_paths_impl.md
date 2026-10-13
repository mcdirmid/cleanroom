<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-11T01:51:09Z
CHANGE: Remove interface-restated catalogs and keep only implementation-specific validation and normalization behavior
CODE_HASH: b34d186d1ab4
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# file_paths_impl implementation component

imports: filesystem_ext
implements: file_paths

## Purpose

The file_paths_impl implementation component realizes path validation and resolution services using host filesystem operations and path normalization.

Manipulating filesystem paths directly without boundary validation risks format inconsistencies and cross-platform path separator mismatches. The file_paths_impl implementation component enforces strict path boundaries by consulting the host filesystem to establish whether a path is absolute and by normalizing path strings into canonical encapsulated records.

**Out of scope:** The file_paths_impl implementation component does not create file aliases, read file contents, or execute filesystem mutations; these are handled by other components.

**Delegated:** Native path inspection and host filesystem checks are delegated to filesystem_ext.

## Types and Behavior

When creating an absolute path, the file path manager establishes absoluteness through the host filesystem, failing when the path string names a location relative to the current working directory or is empty. When creating a workspace path, the file path manager requires a path string naming a location within the workspace without a leading separator, failing when the path string names an absolute location.

Creating or resolving paths normalizes redundant separators and relative directory segments into encapsulated path records, and resolving a workspace path against the absolute path of a workspace root joins the two path strings before normalizing the combination into an absolute path record.
