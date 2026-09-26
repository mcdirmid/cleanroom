# file_paths interface component

## Purpose

The file_paths interface component provides structured path representations and path validation services to prevent path ambiguity, directory traversal vulnerabilities, and path format mismatches across the system.

Manipulating filesystem locations as untyped strings allows invalid path formats, relative paths masquerading as absolute paths, and accidental leaks between host paths and relative workspace paths. The file_paths interface component establishes strongly-typed representations for host paths, absolute paths, and workspace paths, providing a system service to create, validate, and resolve them.

**Out of scope:** The file_paths interface component does not read or write file contents, manage file aliases, or execute filesystem mutations; these are handled by other components.

## Types and Behavior

A *host path* encapsulates a path string to a file or directory on the filesystem of the host operating system.

An *absolute path* is a host path that represents an absolute filesystem path.

A *workspace path* is a host path that represents a relative filesystem path anchored to the root of a workspace without leading path separators.

Workspace and absolute paths can only be created from string paths through a system's *file path manager*, which also validates and resolves path representations. The file path manager assumes only non-empty strings are provided. The file path manager validates a given path string depending on whether an absolute or workspace path is desired.

The file path manager can also resolve a workspace path into an absolute path given the absolute path of a workspace root. 
