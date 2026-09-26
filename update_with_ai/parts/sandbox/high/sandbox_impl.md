# sandbox_impl implementation component

imports: sandbox_file_editor
implements: sandbox

## Purpose

The sandbox_impl implementation component realizes template materialization and modification tracking for agent sessions.

Agent sessions require guaranteed workspace state before tool execution begins and accurate tracking of resulting file modifications. The sandbox_impl implementation component bridges the sandbox boundary to the peer edit manager, delegating starter template materialization and exposing session-wide file modification state.

**Out of scope:** The sandbox_impl implementation component does not parse tool arguments, format diff patches, or manage run outcome termination; these are handled by other components.

## Types and Behavior

The sandbox delegates template materialization and file modification queries.

Querying file modifications delegates to the edit manager. Materializing startup templates delegates to the edit manager to write template content to missing read-write files without overwriting existing files.
