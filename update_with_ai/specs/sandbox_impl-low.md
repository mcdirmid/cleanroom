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

The `SandboxImpl` class implements the `Sandbox` Protocol, providing all operations: `get_tool_definitions`, `read_file`, `write_file`, `edit_file`, `replace_lines`, `search_files`, `verify`, `succeed`, `fail`, `blame`, and `get_write_occurred`.

The implementation:
- Maintains per-run state: the write-occurred flag, the per-file view mode for writable files (plain or line-numbered), and the pre-write snapshots of changed files; nothing persists across runs. No stubbing state is maintained; no prior tool result is ever rewritten.
- Resolves virtual names to full filesystem paths using `file_mappings`
- Enforces policy by checking virtual paths against `readable_paths` and `writable_paths`
- Applies the search result limit
- Uses the filesystem for all read/write operations
- Delegates verification to the injected `verification_callback` when non-null. The callback may perform arbitrary actions (including running shell commands) but must not depend on external state or modify the sandbox's filesystem; guaranteeing this is the assembler's responsibility.
- Conditionally includes tools based on configuration (the blame tool only). The verify tool is always emitted.
- Provides `edit_file` (content-based search-and-replace: one occurrence, or all when `expect_multiple` is set) and `replace_lines` (line-range replace, delete, or insert) as file writes: each sets the write-occurred flag, records the changed file, and produces a result with `supersedes` set (the file's earlier results are stubbed by the agent loop). `edit_file` rejects identical `old_str`/`new_str` (a no-op edit) as an invalid argument, and rejects `old_str`/`new_str` longer than 100 characters with a message advising `replace_lines` (which requires the line-numbered view).
- `write_file` creates new files only: it fails when the file already exists, advising `edit_file` or `replace_lines` for modifications.
- `edit_file` and `replace_lines` fail cleanly when the file does not exist, advising `write_file` for creation.
- `read_file` returns the file's entire content, prefixed with line numbers (`"N \u2502 line"`) only when `include_line_numbers` is set (default: off) and the file is writable; a writable file that already exists on disk is only readable in the line-numbered view — a plain read fails with a message advising `read_file(file_path, include_line_numbers=True)`; a read of a file that is not writable produces a plain inline result.
- `replace_lines` may edit only when the file's current view is line-numbered and the file was read in the line-numbered view since the last write; otherwise it fails advising a numbered read (`read_file(file_path, include_line_numbers=True)`); the failure supersedes nothing and removes nothing.
- After a successful `write_file`, `edit_file`, or `replace_lines`, the file's view mode resets to plain (the write invalidates the line numbers); the result carries the operation's status with `supersedes` set, so the file's earlier results are stubbed by the agent loop and the file's current content is not visible until the agent reads the file again.
- `search_files` renders matches only for files that are not writable; matches in writable files are counted and reported in the note without content; pagination (`offset`/`limit`) pages over rendered matches only.
- Processes operations sequentially
- Captures each file's content at run start on its first write of the run; `verify` with no callback diffs the run's changed files against those snapshots and states that no verification tool is present. `verify` with a callback runs the callback and reports its output and success flag.
- `verify` returns a result with `supersedes` set (it supersedes the earlier non-stubbed verification result), and `content` the verification report — the diff of the run's changed files vs. their run-start snapshots, truncated when it exceeds the diff size limit (default 1000 chars) with a footer reporting the truncated size and full change counts; with a callback it additionally contains the callback's output and success flag followed by succeed() guidance (may be called when passed; when failed, change files and re-verify, or blame/fail to end the run), and with no callback it states that no verification tool is present and that succeed() may now be called. The result's `note` is pinned to `Verification passed.` when the callback succeeded, `Verification failed.` when it failed, and `No verification tool configured.` when no callback is configured.
- Provides error messages that identify the violated policy (policy violations are handled by the sandbox). Messages name the virtual path, never the resolved filesystem path, and list the readable/writable paths.
- Leaves filesystem unchanged on handled errors (policy violations). Filesystem errors and verification-callback exceptions are outside the interface contract; this implementation reports them as tool failures identifying the failing operation.
- Does not persist state across runs
- Sets each result's `supersedes` flag per the `sandbox` interface contract: operations on writable files and `verify` set it; reads of files that are not writable, `search_files`, and termination tools' results do not. The agent loop applies the stubbing.
- `blame` with no configured blame targets returns `ToolFailure[str]` (a precondition violation; the tool is not offered when targets are empty)
- Forms the `TerminateAgentWithSuccess` result using `dag_clean_logic` result types:
  - `succeed` — carries `NoChangeResult()` when no file's current content differs from its run-start snapshot (writes may have occurred but net out to no change), or `ChangeResult` with messages built from `changes` when files changed; rejects a change summary for a net-unchanged file (its content equals its run-start snapshot), and directs a run whose writes all net out to report no change (succeed with no changes)
  - `succeed`'s change summaries are bounded by the sandbox's soft and hard length bounds: a summary over the soft bound is rejected with shortening guidance up to 4 rejections per run, then accepted when within the hard bound; a summary over the hard bound is rejected with hard-bound guidance up to 4 rejections per run, and a succeed call still over the hard bound after that returns `TerminateAgentWithFailure[str]` (the run fails); the rejection counters are per-run, independent, and reset on any accepted summary
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

- **View mode default:** A new writable file's results render plain until the agent reads it with `include_line_numbers=True`; an existing writable file is only readable in the line-numbered view, so its view mode is line-numbered from the first successful read; a write resets the view mode to plain (line numbers invalidated until the next numbered read).
- **Edit length limit:** `edit_file` rejects `old_str`/`new_str` exceeding 100 characters, per the `sandbox` interface contract.
- **Change summary length bounds:** Soft bound pinned to 200 characters, hard bound pinned to 500 characters, grace pinned to 4 rejections per run for each bound; tests may assert the soft/hard rejection messages and the grace transitions (a summary within the hard bound accepted on the succeed call after 4 soft-limit rejections; a summary over the hard bound turning `succeed` into `TerminateAgentWithFailure` on the succeed call after 4 hard-limit rejections).
- **Diff size limit default:** Pinned to 1000 characters when `diff_size_limit` is `None`; tests may assert the truncation footer.
- **T_tool resolution:** The implementation resolves `T_tool` (from `tool_provider`) to `str` in failure signals (`ToolFailure[str]`).
