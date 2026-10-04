# sandbox_file_editor interface component

imports: agent_session, agent_file_alias, tool_provider

## Purpose

The sandbox_file_editor interface component provides safe workspace file editing tools for writable files while preventing arbitrary disk writes.

Autonomous agents require structured mechanisms to update code and configurations, but unrestrained whole-file overwrites risk destroying context, introducing syntax corruption, and bypassing file access permissions. The sandbox_file_editor interface component establishes an isolated editing layer restricted strictly to declared writable files, offering precise replacement and line-bounded writes.

**Out of scope:** The sandbox_file_editor interface component does not manage agent turn loops, execute verification checks, or resolve host file paths; these are handled by other components.

## Types and Behavior

An *editing tool* is a tool that writes to a read-write file.

An agent session's *replace file content tool* is an editing tool that replaces target content with replacement content in a read-write file within a line range bounded by a start line and end line, or across multiple occurrences when multiple replacements are permitted.

An agent session's *edit manager* writes to workspace files and tracks session edits.

The edit manager:

- Exposes whether workspace file writes occurred during the session, determined by whether workspace file contents differ from their initial state prior to editing.

- Computes a *file hash* for a read-write file from its content.

- Exposes a *file update revision* that tracks sequential updates made to workspace files.

- Tracks the *last read or edited file* across the session, recording file reads through *record file read* and recording file edits through *record file edit*.

- Provides a *can write* operation validating write access for a read-write file path.
