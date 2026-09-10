# file_paths interface component

## Purpose

The file_paths interface component provides structured path representations and path validation services to prevent path ambiguity, directory traversal vulnerabilities, and path format mismatches across the system.

Manipulating filesystem locations as untyped strings allows invalid path formats, relative paths masquerading as absolute paths, and accidental leaks between host paths and relative workspace paths. The file_paths interface component establishes strongly-typed representations for host paths, absolute paths, workspace paths, directory paths, and workspace roots, providing a system service to create, validate, and resolve them.

**Out of scope:** The file_paths interface component does not read or write file contents, manage file aliases, or execute filesystem mutations; these are handled by other components.

## Types and Behavior

A *host path* is a value record representing a filesystem path on the host operating system, having a *path* string. A host path is constructed exclusively through service operations rather than direct public constructors.

An *absolute path* is a host path that represents an absolute filesystem path on the host operating system.

A *workspace path* is a host path that represents a relative filesystem path anchored to the root of a workspace without leading path separators.

A *directory path* is an absolute path that represents a directory on the host operating system.

A *workspace root* is a directory path representing the root directory of the workspace.

The *file paths* service is a system service that creates, validates, and resolves path representations. The file paths service:

- *Creates host path* from a path string, assuming the caller supplies a non-empty string, and requiring that the returned host path encapsulates the path string.

- *Creates absolute path* from a path string, assuming the caller supplies a valid absolute path format for the host operating system, and requiring that the returned absolute path encapsulates the path string if the string is absolute, or raises a failure if the string is not absolute.

- *Creates workspace path* from a path string, assuming the caller supplies a valid relative path format without leading separators, and requiring that the returned workspace path encapsulates the path string if the string is relative, or raises a failure if the string is absolute.

- *Creates directory path* from a path string, assuming the caller supplies a valid absolute directory path format for the host operating system, and requiring that the returned directory path encapsulates the path string if the string is absolute, or raises a failure if the string is not absolute.

- *Gets workspace root*, requiring that the returned workspace root represents the physical workspace root directory.

- *Resolves directory* from a workspace root and a workspace path, assuming the workspace path is a relative path within the root, and requiring that the returned directory path is formed by joining the workspace root and the workspace path.

- *Resolves path* from a workspace root and a workspace path, assuming the workspace path is a relative path within the root, and requiring that the returned absolute path is formed by joining the workspace root and the workspace path.
