<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-05T05:21:23Z
CHANGE: Align purpose with sandbox to justify agent_node_config import and add delegation boundary
CODE_HASH: 4793d2f9ef5a
-->

# sandbox_impl implementation component

imports: sandbox_file_editor, dag_storage, agent_node_config
implements: sandbox

## Purpose

The sandbox_impl implementation component realizes template materialization and modification tracking for agent sessions.

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. The sandbox_impl implementation component establishes a unified session coordination boundary that ensures template materialization precedes agent execution, resolving session read-write files and templates from session config, delegating starter template materialization to dag storage, and exposing session-wide file modification state from the edit manager.

**Out of scope:** The sandbox_impl implementation component does not parse tool arguments, format diff patches, or manage run outcome termination; these are handled by other components.

**Delegated:** Session file and template definitions are delegated to agent_node_config; file storage and template materialization are delegated to dag_storage; file modification tracking is delegated to sandbox_file_editor.

## Types and Behavior

The sandbox coordinates workspace state for the active session, ensuring template materialization precedes agent execution.

Materializing startup templates resolves the session read-write files and templates from session config, delegating template materialization to dag storage to write template content to missing read-write files without overwriting existing files.

Querying file modifications delegates to the edit manager.
