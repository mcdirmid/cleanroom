# virtual_file_name

## Purpose

Decouples agent file access from host filesystem paths to ensure hermetic, portable workspace interactions and avoid token waste.

Exposing raw host paths causes models to leak environment-specific details, memorize local directories, and attempt out-of-scope file access. Exposing unnecessary directory hierarchy also bloats prompt context and degrades model targeting. Virtual file names eliminate this by identifying workspace files through minimal unambiguous names stripped of path hierarchy unless required to resolve collisions, ensuring operations remain deterministic, concise, and safe across host environments.

## Types

- A *virtual file name* is a minimal unambiguous path used by an agent to refer to a workspace file (such as a bare filename or a minimally prefixed path segment)
- A *virtual file mapping* is a bidirectional association between *virtual file names* and host file paths
- A *virtual file mapper* is a utility that derives *virtual file mappings* from workspace file paths, translates between host paths and *virtual file names*, and sanitizes text
- A *virtual file mapper factory* is a provider that constructs *virtual file mappers* for collections of workspace file paths

## Behavior

- A *virtual file name* addresses a file within a virtual workspace.
- Each *virtual file name* in a workspace uniquely identifies at most one file.
- Creating a *virtual file mapper* through a *virtual file mapper factory* yields a *virtual file mapper* initialized with *virtual file mappings* for a collection of workspace file paths.
- Resolving a workspace file path (whether given as a full absolute path or a workspace-relative path) to a *virtual file name* uses the bare filename when unique across all accessible workspace files, and prepends minimal parent path segments only to disambiguate collisions.
- A *virtual file mapper* translates a *virtual file name* to its underlying host file path, and a host file path to its corresponding *virtual file name*.
- Transforming text through a *virtual file mapper* replaces occurrences of full absolute paths and workspace-relative paths with *virtual file names* in descending path length order.

