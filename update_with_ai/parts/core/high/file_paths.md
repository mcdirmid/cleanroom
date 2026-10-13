<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Clarify host path creation and restructure prose per high-level spec guide
CODE_HASH: 4116f90d9863
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# file_paths interface component

## Purpose

The file_paths interface component provides structured path representations and path validation services to prevent path ambiguity, directory traversal vulnerabilities, and path format mismatches across the system.

Manipulating filesystem locations as untyped strings allows invalid path formats, relative paths masquerading as absolute paths, and accidental leaks between host paths and relative workspace paths. The file_paths interface component establishes strongly-typed representations for host paths, absolute paths, and workspace paths, providing a system service to create and resolve them.

**Out of scope:** The file_paths interface component does not read or write file contents, manage file aliases, or execute filesystem mutations; these are handled by other components.

## Types and Behavior

A *host path* encapsulates a path string naming a file or directory on the filesystem of the host operating system, without guaranteeing whether the path string is absolute or relative.

An *absolute path* is a host path whose path string names a location from the filesystem root.

A *workspace path* is a host path whose path string names a location relative to the root of a workspace without a leading path separator.

Absolute and workspace paths are created only from string paths through a system's *file path manager*, which also validates and resolves path representations.

The file path manager assumes only non-empty path strings are supplied, and creates a host path directly for a path string naming neither an absolute nor a workspace location.

The file path manager validates a supplied path string against the path kind being created, requiring an absolute path to name a host absolute location and requiring a workspace path to name a host relative location without a leading separator.

The file path manager can also resolve a workspace path into an absolute path given the absolute path of a workspace root.
