# agent_file_alias interface component

imports: agent_session, dag_storage, file_paths, tool_provider

## Purpose

The agent_file_alias interface component decouples agent session file interactions from physical host paths to prevent environment leakage and path collisions.

Exposing raw operating system paths directly to language model agents invites hallucinated absolute paths, introduces cross-environment execution drift, and leaks local host directory structures into context windows. The agent_file_alias interface component creates an isolated virtual addressing space anchored to the active session, shielding the agent from underlying filesystem layouts while ensuring all referenced files correspond to tracked task boundaries and providing standard representations for file contents and search patterns.

**Out of scope:** The agent_file_alias interface component does not read or write file contents on disk, execute tools, or govern node tasks; these are handled by other components.

## Types and Behavior

*File content* represents data read from or stored in a file.

A *regex pattern* represents a pattern used to search in files.

A *file alias* represents a session file, hiding physical filesystem details and paths from the agent, having a relative path that identifies the file within an agent session. When converted to a string, a file alias displays itself by its relative path. 

A file alias is either a *bound file* or an *unbound file*. A bound file is mapped to a workspace file with a workspace path and an owning node, and is either a *read-only file* or a *read-write file*. An unbound file is not mapped to an actual workspace file.

The *alias manager* of an agent session is configured with the absolute path of a workspace root. The alias manager:

- Is a parameter type with the python type file alias and wire type string so file aliases can be tool parameters. Converting a wire type string produces a matching read-only or read-write file, or an unbound file otherwise.

- Sanitizes text by masking occurrences of relative workspace paths and preceding path prefixes with file alias relative paths so that agents observe file aliases rather than environment paths.
