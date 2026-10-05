<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T02:07:35Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 06ce65f13004
-->

# sandbox_impl implementation component

imports: sandbox_file_editor, dag_storage, agent_node_config
implements: sandbox

## Purpose

The sandbox_impl implementation component realizes template materialization and modification tracking for agent sessions.

Agent sessions require guaranteed workspace state before tool execution begins and accurate tracking of resulting file modifications. The sandbox_impl implementation component bridges the sandbox boundary to peer services, delegating starter template materialization to dag storage and exposing session-wide file modification state from the edit manager.

**Out of scope:** The sandbox_impl implementation component does not parse tool arguments, format diff patches, or manage run outcome termination; these are handled by other components.

**Delegated:** File storage and template materialization are delegated to dag_storage; file modification tracking is delegated to sandbox_file_editor.

## Types and Behavior

The sandbox delegates template materialization and file modification queries.

Querying file modifications delegates to the edit manager. Materializing startup templates delegates to dag storage to write template content to missing read-write files without overwriting existing files.
