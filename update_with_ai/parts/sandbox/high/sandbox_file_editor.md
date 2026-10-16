<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: State write detection and the can write capability declaratively and remove redundant lead-ins
CODE_HASH: 861261bf69fd
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# sandbox_file_editor interface component

imports: agent_session, agent_file_alias, tool_provider

## Purpose

The sandbox_file_editor interface component provides safe workspace file editing tools for writable files while preventing arbitrary disk writes.

Autonomous agents require structured mechanisms to update code and configurations, but unrestrained whole-file overwrites risk destroying context, introducing syntax corruption, and bypassing file access permissions. The sandbox_file_editor interface component establishes an isolated editing layer restricted strictly to declared writable files, offering precise replacement and line-bounded writes.

**Out of scope:** The sandbox_file_editor interface component does not manage agent turn loops, execute verification checks, or resolve host file paths; these are handled by other components.

**Delegated:** File alias addressing is delegated to agent_file_alias; tool registration and parameter conversion are delegated to tool_provider; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

An *editing tool* is a tool that writes to a read-write file.

An agent session's *replace file content tool* is an editing tool that replaces target content with replacement content in a read-write file within a line range bounded by a start line and an end line, or across multiple occurrences when multiple replacements are permitted.

An agent session's *edit manager* tracks the edits an agent session makes to workspace files, and exposes whether workspace file writes occurred during the session by comparing workspace file content against its in-band code hash.

The edit manager also computes a *file hash* for a read-write file from its content, exposes a *file update revision* that tracks sequential updates to workspace files, and tracks the *last read or edited file* across the session, recording file reads through *record file read* and file edits through *record file edit*.

The edit manager provides a *can write* capability that validates write access for a read-write file path, so that editing tools establish that a target is writable before attempting a change.
