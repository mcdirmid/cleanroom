<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-05T05:21:23Z
CHANGE: Align purpose with sandbox to justify agent_node_config import and add delegation boundary
CODE_HASH: 4793d2f9ef5a
-->

# sandbox_impl implementation component

imports: sandbox_file_editor
implements: sandbox

## Purpose

The sandbox_impl implementation component realizes modification tracking for agent sessions.

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. The sandbox_impl implementation component establishes a unified session coordination boundary that exposes session-wide file modification state from the edit manager.

**Out of scope:** The sandbox_impl implementation component does not parse tool arguments, format diff patches, or manage run outcome termination; these are handled by other components.

**Delegated:** File modification tracking is delegated to sandbox_file_editor.

## Types and Behavior

The sandbox coordinates workspace state for the active session.

Querying file modifications delegates to the edit manager.
