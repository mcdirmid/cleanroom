<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 32a37c0092de
-->

# sandbox_file_editor interface component

imports: agent_session, agent_file_alias, tool_provider

## Intent

Autonomous agents require structured mechanisms to update code and configurations, but unrestrained whole-file overwrites risk destroying context, introducing syntax corruption, and bypassing file access permissions. Furthermore, multi-stage workflows frequently initialize new tasks with boilerplate starter templates that must not clobber existing implementations. The sandbox_file_editor interface component establishes an isolated editing layer restricted strictly to declared writable files, offering precise replacement and line-bounded writes alongside non-destructive template initialization.

By tracking file modifications, revision numbers, and the most recently accessed files, the edit manager enables downstream verification services to determine whether meaningful work was accomplished during an agent turn.

## Factored Contracts

### Typing

- An editing tool is a tool that writes to a read-write file.
- The replace file content tool specifies a read-write file target parameter.
- The replace file content tool specifies target content and replacement content parameters.
- The replace file content tool specifies start line and end line range parameters.
- The replace file content tool specifies an allow multiple parameter.

### Contracts

- A caller supplies a read-write file when validating write access. [validate_write_access_supplied]
- A caller supplies a file alias when recording file reads. [record_read_supplied]
- A caller supplies a file alias when recording file edits. [record_edit_supplied]
- The edit manager writes to workspace files for an agent session. [edit_mgr_writes_workspace]
- The edit manager tracks session edits across an agent session. [edit_mgr_tracks_session_edits]
- The edit manager exposes whether workspace file writes occurred during the session. [expose_workspace_writes_occurred]
- The edit manager computes a file hash for a read-write file from its content. [compute_file_hash]
- The edit manager exposes a file update revision tracking sequential workspace updates. [expose_file_update_revision]
- The edit manager tracks the last read or edited file across the session. [track_last_read_or_edited]
- The edit manager records file reads through record file read. [record_file_read_op]
- The edit manager records file edits through record file edit. [record_file_edit_op]
- The edit manager provides a can write operation validating write access for a read-write file. [can_write_validates_access]
- The replace file content tool replaces target content with replacement content within the bounded line range. [replace_content_in_line_range]
- The replace file content tool replaces multiple occurrences when multiple replacements are permitted. [replace_multiple_when_permitted]
- Workspace file writes occurred is true when file contents differ from their in-band code hash. [writes_occurred_true_on_diff]
- Workspace file writes occurred is false when file contents match their in-band code hash. [writes_occurred_false_on_match]

### Woven Contracts

- Recording file reads updates the tracked last read or edited file in the session. [record_read_supplied, track_last_read_or_edited, record_file_read_op]
- Recording file edits updates the tracked last read or edited file in the session. [record_edit_supplied, track_last_read_or_edited, record_file_edit_op]
- The replace file content tool replaces target content within the designated line range or across multiple occurrences when allowed. [replace_content_in_line_range, replace_multiple_when_permitted, tool_provider: [call_by_name, call_with_python_bindings]]
- Workspace file writes status reflects whether current workspace file contents differ from their in-band code hash. [edit_mgr_tracks_session_edits, expose_workspace_writes_occurred, writes_occurred_true_on_diff, writes_occurred_false_on_match]

## Grounding

### Knowledge Provisions

- Exposes whether workspace file writes occurred during the session. [writes_occurred_status]
- Validates write access for declared read-write files. [write_access_validation]
- Replaces file content within bounded line ranges. [content_replacement]
- Tracks sequential file update revisions. [update_revision_tracking]

### Knowledge Requirements

- Access to underlying filesystem to read and write file contents.
  - Deferred: Requires concrete filesystem operations in implementation.
- Verification of declared read-write files against session node configuration.
  - Deferred: Requires session configuration inspection in implementation.
- Tracking of file read and edit history in session state.
  - Deferred: Requires session state tracking in implementation.
