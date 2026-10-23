# file_editor interface component

imports: session, file_alias, tool_provider, file_reader

## Purpose

The file_editor interface component provides safe workspace file editing tools for writable files while preventing arbitrary disk writes.

Autonomous agents require structured mechanisms to update code and configurations, but unrestrained whole-file overwrites risk destroying context, introducing syntax corruption, and bypassing file access permissions. The file_editor interface component establishes an isolated editing layer restricted strictly to declared writable files, offering precise replacement and line-bounded writes.

**Out of scope:** The file_editor interface component does not manage agent turn loops, execute verification checks, or resolve host file paths; these are handled by other components.

**Delegated:** File alias addressing is delegated to agent_file_alias; tool registration and parameter conversion are delegated to tool_provider; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

An agent session's *editing tool* is a tool that writes to a read-write file, declaring target path and line range parameters.

An agent session's *replace file content tool* is an editing tool that replaces target content with replacement content in a read-write file within a line range bounded by a start line and an end line, attempting whitespace-normalized line matching when exact character-sequence matching fails and matches uniquely within the target line range, rejecting any modification that alters or removes in-band metadata header blocks, appending a unified diff to tool response output when edit delta formatting is enabled, or operating across multiple occurrences when multiple replacements are permitted. When consecutive replacement attempts fail, the replace file content tool issues a warning reminder at two consecutive failures and designates a follow-up tool call to view the target file using the session's file viewing tool if the target file is present, and terminates with failure when reaching four consecutive failed replacement attempts.

An agent session's *edit manager* tracks the edits an agent session makes to workspace files, and exposes whether workspace file writes occurred during the session by comparing workspace file content against its in-band code hash.

The edit manager also computes a *file hash* for a read-write file from its content, exposes a *file update revision* that tracks sequential updates to workspace files, and tracks the *last read or edited file* across the session, recording file reads through *record file read* and file edits through *record file edit*.

The edit manager provides a *can write* capability that validates write access for a read-write file path, so that editing tools establish that a target is writable before attempting a change.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-21T21:20:00Z
LAST_CHANGED: 2026-10-21T21:20:00Z
CHANGE: Specify consecutive replacement failure warnings with follow-up file view and fatal termination
SPEC_QA_AUDIT: 2026-10-21T21:20:00Z
-->
