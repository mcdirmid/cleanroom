# file_editor

imports: file_reader (virtual name, line-numbered view), tool_provider (tool results, supersession flag, tool failure, tool call)
terms (from file_reader): virtual name, line-numbered view
terms (from tool_provider): tool result, supersession flag, tool failure, tool call
terms (owned): file write, injected read, template

## Purpose

Provides file modification and change tracking: content-based text replacement, line-range editing, template initialization, post-write re-reads, and run-level write state tracking. Enforces write permissions.

## Terms

- File write: a mutation operation (replace or update_lines) that alters a writable file on disk.
- Injected read: an automatic re-read of a file with line numbers injected into the conversation following a successful write.
- Template: initial content materialized to a writable file at startup if the file does not already exist on disk.

## Contract

**Inputs**

- Per edit: a virtual file path, search/replace strings, line range, or templates.

**Operations**

- Replace short text in a file (content-based replacement up to 200 characters).
- Update lines in a file by 1-indexed line range (replacement, deletion, or insertion).
- Query whether any file write occurred during the session.
- Query changed files, current content, and baseline run-start snapshots.

**Guarantees**

- Edits are allowed only on declared writable files.
- A successful write sets the write-occurred flag, invalidates the previous view, updates the changed file list, and produces a write confirmation followed by an injected line-numbered read.
- Both the write confirmation and injected read set the supersession flag.
- Updating lines requires an active line-numbered view from the most recent read.
- Templates are created at startup only for missing writable files; existing files are never overwritten.
- Template initialization does not set the write-occurred flag.
- No state persists across sessions.

**Assumptions**

- Files are UTF-8 encoded.

## Non-concerns

- Diff generation: handled by run_control using baseline snapshots from file_editor.
