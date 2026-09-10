# file_paths_impl implementation component

imports: file_paths, filesystem_ext
implements: file_paths

## Purpose

The file_paths_impl implementation component provides the concrete implementation of the file paths service using the filesystem boundary and operating system environment.

Accurate path validation and resolution require consulting the physical host operating system layout, environment variables indicating workspace boundaries, and platform-specific path mechanics. The file_paths_impl component implements the file paths service by delegating to host filesystem functions to validate path formats and resolve workspace roots.

**Out of scope:** The file_paths_impl component does not create file aliases or interact with language models; these are handled by other components.

## Types and Behavior

The *file paths* implementation is a system service implementing the file paths interface. The file paths implementation:

- Implements *create host path* by instantiating a host path record holding the path string.

- Implements *create absolute path* by verifying that the path string is absolute using the host filesystem, raising a failure if it is not, and instantiating an absolute path record holding the path string.

- Implements *create workspace path* by verifying that the path string is not absolute using the host filesystem, raising a failure if it is absolute, and instantiating a workspace path record holding the path string.

- Implements *create directory path* by verifying that the path string is absolute using the host filesystem, raising a failure if it is not, and instantiating a directory path record holding the path string.

- Implements *get workspace root* by checking the environment for the workspace directory variable, falling back to the current working directory, and instantiating a workspace root record holding the resolved directory path.

- Implements *resolve directory* by joining the workspace root path and relative workspace path, and instantiating a directory path record holding the joined path.

- Implements *resolve path* by joining the workspace root path and relative workspace path, and instantiating an absolute path record holding the joined path.
