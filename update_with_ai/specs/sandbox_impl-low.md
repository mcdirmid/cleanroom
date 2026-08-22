<!-- Dependencies (md files to read alongside this one):
  - sandbox-low.md
  - tool_provider-low.md
  - dag_clean_logic-low.md
  - agent_loop-low.md
-->

# Implementation LLS: sandbox_impl

## Data Types
```python
from sandbox import (
    Sandbox,
    SandboxConfig,
    VirtualName,
    FilePath,
    WriteOccurred,
)
from tool_provider import (
    ToolDefinition,
    ToolResult,
    PresentedToolResult,
    ToolCallOutcome,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
    ToolFailure,
)
from dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult

class SandboxImpl(Sandbox):
    def __init__(self, config: SandboxConfig): ...
```

Constructed with the `sandbox` interface's `SandboxConfig` (see Interface LLS Data Types); it bundles no imported capabilities.

## Behavioral Description

The `SandboxImpl` class implements the `Sandbox` Protocol, providing all operations: `get_tool_definitions`, `read_file`, `write_file`, `edit_file`, `replace_lines`, `search_files`, `advance`, `fail`, `blame`, `get_session_start_reads`, and `get_write_occurred`.

The implementation:
- Maintains per-run state: the write-occurred flag, the per-file view mode for writable files (plain or line-numbered), and the pre-write snapshots of changed files; nothing persists across runs. No stubbing state is maintained; no prior tool result is ever rewritten.
- Resolves virtual names to full filesystem paths using `file_mappings`
- Enforces policy by checking virtual paths against `readable_paths` and `writable_paths`
- Applies the search result limit
- Uses the filesystem for all read/write operations
- Delegates verification to the injected `verification_callback` when non-null. The callback may perform arbitrary actions (including running shell commands) but must not depend on external state or modify the sandbox's filesystem; guaranteeing this is the assembler's responsibility.
- Conditionally includes tools based on configuration (the blame tool only). The advance tool is always emitted.
- Provides `edit_file` (content-based search-and-replace: one occurrence, or all when `expect_multiple` is set) and `replace_lines` (line-range replace, delete, or insert) as file writes: each sets the write-occurred flag, records the changed file, and produces an outcome of two results — a write confirmation with `supersedes` set and an injected read (a `PresentedToolResult` pairing `read_file(file_path, include_line_numbers=True)` with the file's numbered content, `supersedes` set); the agent loop applies the stubbing. `edit_file` rejects identical `old_str`/`new_str` (a no-op edit) as an invalid argument, and rejects `old_str`/`new_str` longer than 100 characters with a message advising `replace_lines` (which requires the line-numbered view).
- `write_file` creates new files only: it fails when the file already exists, advising `edit_file` or `replace_lines` for modifications.
- `edit_file` and `replace_lines` fail cleanly when the file does not exist, advising `write_file` for creation.
- `read_file` returns the file's entire content, prefixed with line numbers (`"N \u2502 line"`) only when `include_line_numbers` is set (default: off) and the file is writable; a writable file that already exists on disk is only readable in the line-numbered view — a plain read fails with a message advising `read_file(file_path, include_line_numbers=True)`; a read of a file that is not writable produces a plain inline result.
- Provides the session-start reads: when `session_start_reads_enabled` is set, a plain read (never superseding) of every configured file that is readable but not writable and exists as a regular file on disk, sorted by virtual name; each is a `PresentedToolResult` pairing `read_file(file_path)` with the plain read result (the session-start reads change no sandbox state).
- `replace_lines` may edit only when the file's current view is line-numbered (a write resets the view to plain; the injected read after a write re-enables the line-numbered view); otherwise it fails advising a numbered read (`read_file(file_path, include_line_numbers=True)`); the failure supersedes nothing and removes nothing.
- After a successful `write_file`, `edit_file`, or `replace_lines`, the file's view mode resets to plain (the write invalidates the line numbers) and the injected read that follows re-enables the line-numbered view; the write confirmation carries the operation's status with `supersedes` set and the injected read carries the file's numbered content, so the file's current content is visible in the conversation immediately after the write.
- The injected read follows the write confirmation immediately; both precede the results of any subsequent tool call.
- The injected read is rendered from the file's post-write content in the line-numbered view, restoring the file's line-numbered view state; no additional per-run state is required.
- A write that fails provides no injected read.
- `search_files` renders matches only for files that are not writable; matches in writable files are counted and reported in the note without content; pagination (`offset`/`limit`) pages over rendered matches only.
- Processes operations sequentially
- Captures each file's content at run start on its first write of the run; `advance` diffs the run's changed files against those snapshots (truncated when it exceeds the diff size limit, default 1000 chars, with a footer reporting the truncated size and full change counts) and, when a callback is configured, runs the callback; when no callback is configured, verification is treated as passed.
- `advance` on a failing verification provides feedback — a result with `supersedes` set (it supersedes the earlier non-stubbed verification result), `content` the verification failure details and guidance (change files and call advance again, or blame/fail to end the run; never the run's diff), and `note` pinned to `Verification failed.`; the session continues and advance never terminates on a failing verification.
- `advance` on a passing verification (or no callback) signals successful termination: with no net change it carries `NoChangeResult()`; when files changed it requires `changes` — a missing `changes` signals a `ToolFailure[str]` listing the changed files and showing the run's diff, and a valid `changes` carries `ChangeResult` with messages built from it.
- Provides error messages that identify the violated policy (policy violations are handled by the sandbox). Messages name the virtual path, never the resolved filesystem path, and list the readable/writable paths.
- Leaves filesystem unchanged on handled errors (policy violations). Filesystem errors and verification-callback exceptions are outside the interface contract; this implementation reports them as tool failures identifying the failing operation.
- Does not persist state across runs
- Sets each result's `supersedes` flag per the `sandbox` interface contract: operations on writable files and advance's verification feedback set it; reads of files that are not writable, `search_files`, and termination tools' results do not. The agent loop applies the stubbing.
- `blame` with no configured blame targets returns `ToolFailure[str]` (a precondition violation; the tool is not offered when targets are empty)
- Forms the `TerminateAgentWithSuccess` result using `dag_clean_logic` result types:
  - `advance` — carries `NoChangeResult()` when no file's current content differs from its run-start snapshot (writes may have occurred but net out to no change), or `ChangeResult` with messages built from `changes` when files changed; rejects a change summary for a net-unchanged file (its content equals its run-start snapshot), and directs a run whose writes all net out to report no change (advance with no changes)
  - `advance`'s change summaries are bounded by the sandbox's soft and hard length bounds: a summary over the soft bound is rejected with shortening guidance up to 4 rejections per run, then accepted when within the hard bound; a summary over the hard bound is rejected with hard-bound guidance up to 4 rejections per run, and an advance call still over the hard bound after that returns `TerminateAgentWithFailure[str]` (the run fails); the rejection counters are per-run, independent, and reset on any accepted summary
  - `blame` (valid pairs) — carries `FeedbackResult(messages=blames)` (each pair is one (target, feedback) message)

**HLS Justification:** Uses the filesystem directly and delegates verification when configured.

## Invariants

- No state persists between runs
- Write-occurred flag set immediately upon successful write and never cleared
- Pre-write snapshots are captured before the run's first write of each file and reset each run
- All file operations use resolved filesystem paths, not virtual names
- Verification callback has no filesystem side effects
- All policy checks occur before any filesystem mutation
- Errors leave the filesystem unchanged
- A write or edit sets `supersedes` on its result; the file's earlier results are stubbed by the agent loop
- A tool result never carries the stub text; the stub text is applied by the agent loop when a result supersedes an earlier one

## Non-Concerns

- **View mode default:** A new writable file's results render plain until the agent reads it with `include_line_numbers=True`; an existing writable file is only readable in the line-numbered view, so its view mode is line-numbered from the first successful read; a write resets the view mode to plain, and the injected read that follows the write re-enables the line-numbered view.
- **Edit length limit:** `edit_file` rejects `old_str`/`new_str` exceeding 100 characters, per the `sandbox` interface contract.
- **Change summary length bounds:** Soft bound pinned to 200 characters, hard bound pinned to 500 characters, grace pinned to 4 rejections per run for each bound; tests may assert the soft/hard rejection messages and the grace transitions (a summary within the hard bound accepted on the advance call after 4 soft-limit rejections; a summary over the hard bound turning `advance` into `TerminateAgentWithFailure` on the advance call after 4 hard-limit rejections).
- **Diff size limit default:** Pinned to 1000 characters when `diff_size_limit` is `None`; tests may assert the truncation footer.
- **T_tool resolution:** The implementation resolves `T_tool` (from `tool_provider`) to `str` in failure signals (`ToolFailure[str]`).
