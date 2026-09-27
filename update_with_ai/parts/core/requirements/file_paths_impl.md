# file_paths_impl implementation component

imports: filesystem_ext
implements: file_paths

## Assumptions and Requirements

### Assumptions

1. The caller supplies valid path strings according to the host operating system.

### Requirements

2. The file path manager validates and resolves path representations using the host filesystem.
3. Creating a host path encapsulates the non-empty path string into a normalized host path record.
4. Creating an absolute path validates that the path string is absolute according to the host filesystem and produces an absolute path record.
5. Creating an absolute path raises a failure when the provided path string is relative.
6. Creating a workspace path validates that the path string is relative without leading separators and produces a workspace path record.
7. Creating a workspace path raises a failure when the provided path string is absolute.
8. Resolving a workspace path against the absolute path of a workspace root joins the relative workspace path to the root path using the host filesystem, producing a normalized absolute path record.

## Grounding Facts

### Knowledge Needed

- Host filesystem absolute path semantics.
- Host filesystem relative path separators.

### Actions Needed

- Validate absolute path using host filesystem.
- Validate relative path without leading separators.
- Join relative path to workspace root path.
