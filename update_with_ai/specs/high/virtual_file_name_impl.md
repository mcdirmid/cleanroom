# virtual_file_name_impl

imports: virtual_file_name
types from virtual_file_name: virtual file name, virtual file mapping, virtual file mapper, virtual file mapper factory
implements: virtual file mapper factory

## Purpose

Implements virtual file name mapping and path sanitization by normalizing host paths against workspace roots and computing minimal disambiguated parent suffixes.

## Behavior

- Creating a *virtual file mapper* through a *virtual file mapper factory* yields a *virtual file mapper* initialized with *virtual file mappings* for a collection of workspace file paths.
- A *virtual file mapper* normalizes absolute host paths by stripping the workspace root directory into workspace-relative paths.
- A *virtual file mapper* computes minimal unique *virtual file names* for all configured workspace files by selecting bare filenames when distinct, and prepending shortest unique parent path segments when collisions occur.
- A *virtual file mapper* maps each *virtual file name* to its resolved host file path, and each host file path to its *virtual file name*.
- Transforming text through a *virtual file mapper* replaces occurrences of absolute host paths and workspace-relative paths with *virtual file names* in descending order of path length.
