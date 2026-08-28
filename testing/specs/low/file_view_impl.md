<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - file_view.md
-->

# Implementation LLS: file_view_impl

## Data Types
```python
from file_view import FileView, FileViewConfig
from tool_provider import PresentedToolResult, ToolFailure, T_tool

class FileViewImpl(FileView):
    def __init__(self, config: FileViewConfig): ...
```

Constructed with the `file_view` interface's `FileViewConfig` (see Interface LLS Data Types); it bundles no imported capabilities. Implements the `FileView` Protocol, providing all operations: `get_tool_definitions`, `get_session_start_reads`, `read_file`, `edit_file`, `replace_lines`, `search_files`, and `get_write_occurred`.

## Behavioral Description

The implementation:
- Maintains per-run state: the write-occurred flag, the per-file view mode for writable files (plain or line-numbered), and the pre-write snapshots of changed files; nothing persists across runs. No stubbing state is maintained; no prior tool result is ever rewritten.
- Resolves virtual names to full filesystem paths using `file_mappings`
- Enforces policy by checking virtual paths against `readable_paths` and `writable_paths`
- Applies the search result limit
- Uses the filesystem directly for all read/write operations
- Provides the file tools, each as a fixed function: reading the entire file, writing, content-based editing, line-range editing, and searching
- Provides `edit_file` (content-based search-and-replace: one occurrence, or all when `expect_multiple` is set) and `replace_lines` (line-range replace, delete, or insert) as file writes: each sets the write-occurred flag, records the changed file, and produces an outcome of two results — a write confirmation with `supersedes` set and an injected read (a `PresentedToolResult` pairing `read_file(file_path, include_line_numbers=True)` with the file's numbered content, `supersedes` set); the agent loop applies the stubbing. `edit_file` rejects identical `old_str`/`new_str` (a no-op edit) as an invalid argument, and rejects `old_str`/`new_str` longer than 100 characters with a message advising `replace_lines` (which requires the line-numbered view).
- `edit_file` and `replace_lines` fail cleanly when the file does not exist (they modify existing files only).
- `read_file` returns the file's entire content, prefixed with line numbers (`"N │ line"`) only when `include_line_numbers` is set (default: off) and the file is writable; a writable file that already exists on disk is only readable in the line-numbered view — a plain read fails with a message advising `read_file(file_path, include_line_numbers=True)`; a read of a file that is not writable produces a plain inline result.
- Provides the session-start reads: when `session_start_reads_enabled` is set, a plain read (never superseding) of every configured file that is readable but not writable and exists as a regular file on disk, sorted by virtual name; each is a `PresentedToolResult` pairing `read_file(file_path)` with the plain read result; the session-start reads change no file_view state.
- Initializes writable files from their templates when file_view is configured: when `templates` has an entry for a writable file that does not exist on disk, the file is created with exactly the template's content before any tool call; an existing writable file is never modified. Initialization is not a file write: it does not set the write-occurred flag and does not record the file as changed.
- `replace_lines` may edit only when the file's current view is line-numbered (a write resets the view to plain; the injected read after a write re-enables the line-numbered view); otherwise it fails advising a numbered read (`read_file(file_path, include_line_numbers=True)`); the failure supersedes nothing and removes nothing.
- After a successful `edit_file` or `replace_lines`, the file's view mode resets to plain (the write invalidates the line numbers) and the injected read that follows re-enables the line-numbered view; the write confirmation carries the operation's status with `supersedes` set and the injected read carries the file's numbered content, so the file's current content is visible in the conversation immediately after the write.
- The injected read follows the write confirmation immediately; both precede the results of any subsequent tool call.
- The injected read is rendered from the file's post-write content in the line-numbered view, restoring the file's line-numbered view state; no additional per-run state is required.
- A write that fails provides no injected read.
- `search_files` renders matches only for files that are not writable; matches in writable files are counted and reported in the note without content; pagination (`offset`/`limit`) pages over rendered matches only.
- Processes operations sequentially.
- Captures each file's content at run start on its first write of the run (a file initialized from its template exists at run start, so its snapshot is the template's content).
- Provides error messages that identify the violated policy (policy violations are handled by file_view). Messages name the virtual path, never the resolved filesystem path, and list the readable/writable paths.
- Leaves the filesystem unchanged on handled errors (policy violations). Filesystem errors are outside the interface contract; this implementation reports them as `ToolFailure[T_tool]` signals identifying the failing operation.
- Does not persist state across runs.
- Sets each result's `supersedes` flag per the `file_view` interface contract: operations on writable files set it; reads of files that are not writable and `search_files` do not. The agent loop applies the stubbing.

**HLS Justification:** Uses the filesystem directly for all file operations and provides the file tools, each as a fixed function.

## Invariants

- No state persists between runs
- A writable file with a template that did not exist at configuration exists with the template's content before any tool call; initialization never sets the write-occurred flag and never records a changed file
- The write-occurred flag is set immediately upon a successful write
- Pre-write snapshots are captured before the run's first write of each file and reset each run
- A write or edit sets `supersedes` on its results; the file's earlier results are stubbed by the agent loop

## Non-Concerns

- **View mode default:** A new writable file's results render plain until the agent reads it with `include_line_numbers=True`; an existing writable file is only readable in the line-numbered view, so its view mode is line-numbered from the first successful read; a write resets the view mode to plain, and the injected read that follows the write re-enables the line-numbered view.
- **Edit length limit:** `edit_file` rejects `old_str`/`new_str` exceeding 100 characters, per the `file_view` interface contract.
- **Error message wording:** error messages identify the violated policy or the failing operation; their exact wording is unspecified.
- **Virtual-name derivation:** the exact procedure that selects the shortest unique suffix is unspecified; the resulting virtual names follow the virtual name definition.
- **Multiple-occurrence edits:** an edit without `expect_multiple` applies to the first occurrence.
