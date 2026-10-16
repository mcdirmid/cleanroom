<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Express alias manager parameter conversion as a delegated capability and restructure the alias operation list
CODE_HASH: 6e0724c0c3c9
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# agent_file_alias interface component

imports: agent_session, dag_storage, file_paths

## Purpose

The agent_file_alias interface component decouples agent session file interactions from physical host paths to prevent environment leakage and path collisions.

Exposing raw operating system paths directly to language model agents invites hallucinated absolute paths, introduces cross-environment execution drift, and leaks local host directory structures into context windows. The agent_file_alias interface component creates an isolated virtual addressing space anchored to the active session, shielding the agent from underlying filesystem layouts while ensuring all referenced files correspond to tracked task boundaries.

**Out of scope:** The agent_file_alias interface component does not read or write file contents on disk, execute tools, or govern node tasks; these are handled by other components.

**Delegated:** Workspace path construction is delegated to file_paths; bound file ownership is delegated to dag_storage.

## Types and Behavior

*File content* represents data read from or stored in a file.

A *regex pattern* represents a pattern used to search in files.

A *file alias* represents a session file, hiding physical filesystem details and paths from the agent, and has a relative path that identifies the file within an agent session. A file alias displays itself by its relative path when converted to a string.

A file alias is either a *bound file* or an *unbound file*. A bound file is mapped to a workspace file with a workspace path and an owning node, and is either a *read-only file* or a *read-write file*. An unbound file is not mapped to a workspace file.

An agent session's *alias manager* is configured with the absolute path of a workspace root, and resolves a string path into a file alias via *to alias*, converting a string that names a declared bound file into that bound file and converting any other string into an unbound file.

The alias manager also sanitizes text by masking occurrences of relative workspace paths and preceding path prefixes with file alias relative paths, preventing the agent from observing host filesystem structure.
