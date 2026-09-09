# file_alias interface component

imports: dag_storage, tool_provider

## Purpose

The file_alias interface component decouples agent session file interactions from physical host paths to prevent environment leakage and path collisions, while providing foundational filesystem data types.

Exposing raw operating system paths directly to language model agents invites hallucinated absolute paths, introduces cross-environment execution drift, and leaks local host directory structures into context windows. The file_alias interface component creates an isolated virtual addressing space anchored to the active session, shielding the agent from underlying filesystem layouts while ensuring all referenced files correspond to tracked task boundaries and providing standard representations for host paths, file contents, and search patterns.

**Out of scope:** The file_alias interface component does not inspect or modify file contents on disk, execute tools, or govern node tasks; these are handled by other components.

## Types and Behavior

A *host path* represents a path on the local filesystem, which can be an *absolute path*, a *directory path*, or a *workspace path* that is relative to the root of the workspace. A *workspace root* is a directory path such that concatenating the workspace root and a workspace path produces an absolute path.

*File content* represents data read from or stored in a file.

A *regex pattern* represents a pattern used to search in files.

A *file alias* represents a session file, hiding physical filesystem details and paths from the agent. A file alias has a *short name* that is assumed to be a minimal unambiguous relative path identifying the file within an agent session. A file alias always displays itself by its short name when converted to a string so that it communicates itself correctly to the agent. A file alias can either be a *bound file* or an *unbound file*.

A bound file is mapped to an actual workspace file, having a *workspace path* and an *owning node*, and can either be a *read-only file* restricted to inspection, or a *read-write file* permitted for inspection and modification. An unbound file is not mapped to an actual file.

The *alias manager* is an agent session service configured with a workspace root that sanitizes output text. The alias manager:

- Is a parameter converter for the actual type file alias and the wire type string, allowing file aliases to be used as tool parameters. Converting a wire type string produces the matching file alias if its short name is found, and produces an unbound file if the short name is not found.

- *Sanitizes* text by *masking* occurrences of host paths with short names so that agents observe file aliases rather than environment paths.
