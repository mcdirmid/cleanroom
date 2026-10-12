<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: State the delegated capability as a declarative report rather than a query
CODE_HASH: c225f9618ae0
SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
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

The sandbox reports whether workspace file modifications occurred during the session by delegating to the edit manager.
