# file_paths_impl implementation component

imports: filesystem_ext
implements: file_paths

## Purpose

The file_paths_impl implementation component provides the concrete implementation of the file paths service using the filesystem boundary and operating system environment.

Accurate path validation and resolution require consulting the physical host operating system layout, environment variables indicating workspace boundaries, and platform-specific path mechanics. The file_paths_impl implementation component realizes the file paths service by delegating to host filesystem functions to validate path formats and resolve workspace roots.

**Out of scope:** The file_paths_impl implementation component does not create file aliases or interact with language models; these are handled by other components.

## Types and Behavior

The file paths implementation is a system service implementing the file paths interface.

Host paths encapsulate non-empty path strings. Absolute paths and directory paths validate that path strings are absolute according to the host filesystem, raising a failure when relative, and normalize path representations into encapsulated records.

Workspace paths validate that path strings are relative, raising a failure when absolute, and normalize relative path representations into encapsulated records.

Workspace root discovery inspects the process environment for the workspace directory variable, falling back to the current working directory when unset or not absolute, and returns a workspace root encapsulating the normalized absolute directory path.

Resolving paths and directories against a workspace root joins the relative workspace path to the workspace root directory path, producing normalized absolute path or directory path records.
