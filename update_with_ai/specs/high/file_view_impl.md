# file_view_impl

fulfills: file_view
imports: tool_provider (tool results, tool failures)
terms (from tool_provider): supersession flag
terms (from file_view): virtual name, file write, line-numbered view, injected read, session-start read, template
terms (refined): virtual name

## Deltas

- [refines] virtual name -> the implementation addresses every configured file by its virtual name — the file's final path component, or the shortest path suffix unique among the configured files — and never presents a file's full path to the agent: reads, writes, edits, searches, session-start reads, and error messages name files by virtual name.
- Uses the filesystem directly for all file operations.
- Provides the file tools, each as a fixed function: reading the entire file, writing, content-based editing, line-range editing, searching.
- A read of a writable file supersedes the earlier result for that file; a write, a content-based edit, and a line-range edit supersede the earlier result for that file.
- Sets the supersession flag on the results of operations on writable files, never on reads of files that are not writable or on searches.
- The superseded result is identified by the file's virtual name.
- A successful write, content-based edit, or line-range edit provides a write confirmation and an injected read (a numbered read of the file).
- The write confirmation's content is the operation's status, never a file-content echo.
- [state] Supersession is matched by the file's virtual name; no separate identity is introduced.
- Provides the session-start reads: when enabled, a plain read (never superseding) of every configured file that is readable but not writable and exists as a regular file on disk, sorted by virtual name.
- A writable file with a configured template that does not exist on disk is created when the component is configured, before any tool call.
- [state] A file initialized from its template is run-start state: its pre-write snapshot is the template's content.
- [ordering] Tool calls are processed sequentially; the write-occurred flag is set immediately upon a successful file write.
- [ordering] The injected read follows the write confirmation immediately; both precede the results of any subsequent tool call.
- [state] Per-run state only: the write-occurred flag, the per-file view modes, and the pre-write snapshots; nothing persists across runs. No stubbing state is maintained.
- [state] The injected read renders the file's post-write content in the line-numbered view, restoring the file's line-numbered view state; no additional per-run state is required.
- [state] A read sets the file's view — plain or line-numbered — per run; a write resets the view to plain, invalidating the line numbers, and the injected read that follows re-enables the line-numbered view.
- [external] The filesystem.
- [failure] A write that fails provides no injected read.

## Non-concerns

- View handling: the exact mechanism for tracking per-file view modes is unspecified.
