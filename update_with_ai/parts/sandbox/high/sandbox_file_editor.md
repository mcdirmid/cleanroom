# sandbox_file_editor interface component

imports: tool_provider, agent_file_alias

## Purpose

The sandbox_file_editor interface component provides safe workspace file editing tools and template materialization for writable files while preventing arbitrary disk writes.

Autonomous agents require structured mechanisms to update code and configurations, but unrestrained whole-file overwrites risk destroying context, introducing syntax corruption, and bypassing file access permissions. Furthermore, multi-stage workflows frequently initialize new tasks with boilerplate starter templates that must not clobber existing implementations. The sandbox_file_editor interface component establishes an isolated editing layer restricted strictly to declared writable files, offering precise replacement and line-bounded modifications alongside non-destructive template initialization.

**Out of scope:** The sandbox_file_editor interface component does not manage agent turn loops, execute verification checks, or resolve host file paths; these are handled by other components.

## Types and Behavior

A *template* is file content representing initial boilerplate for a read-write file.

An *editing tool* is a tool that modifies a read-write file.

The *edit manager* is an agent session service that modifies workspace files and tracks session edits. The edit manager installs:

- A *replace file content tool* that is an editing tool replacing target content in a read-write file within an optional line range, accepting a *file alias parameter*, a *target content parameter*, a *replacement content parameter*, a *start line parameter*, an *end line parameter*, and an *allow multiple parameter*.

The edit manager can *materialize* templates into missing read-write files at session start without overwriting existing files. The edit manager exposes whether workspace file *modifications* occurred during the session, determined by whether workspace file contents differ from their initial state prior to editing, and exposes a *file update revision* that tracks sequential updates made to workspace files. The edit manager tracks the *last read or edited file* across the session, recording file reads from file readers and file edits from editing tools.
