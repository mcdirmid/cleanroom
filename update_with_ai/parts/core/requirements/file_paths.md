# file_paths interface component

## Assumptions and Requirements

### Assumptions

1. The caller supplies a non-empty string when creating a host path, absolute path, or workspace path.

### Requirements

2. A host path encapsulates a path string to a file or directory on the filesystem of the host operating system.
3. An absolute path is a host path representing an absolute filesystem path.
4. A workspace path is a host path representing a relative filesystem path anchored to the root of a workspace without leading path separators.
5. Creating a host path through the file path manager returns a host path encapsulating the given path string.
   - (woven with assumption [1]): The returned host path encapsulates the non-empty path string.
6. Creating an absolute path through the file path manager validates that the path string is an absolute path and returns an absolute path encapsulating the path string.
   - (woven with assumption [1]): The returned absolute path encapsulates the non-empty absolute path string.
7. Creating a workspace path through the file path manager validates that the path string is a relative path without leading path separators and returns a workspace path encapsulating the path string.
   - (woven with assumption [1]): The returned workspace path encapsulates the non-empty relative workspace path string without leading path separators.
8. Resolving a workspace path into an absolute path given the absolute path of a workspace root returns an absolute path formed by joining the workspace root and the workspace path.

## Grounding Facts

### Knowledge Needed

- Raw path string.
- Workspace root absolute path.
- Absolute vs relative path validation rules.

### Actions Needed

- Validate and construct host path, absolute path, or workspace path.
- Resolve workspace path against workspace root into absolute path.
