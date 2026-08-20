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
```

```python
class SandboxImpl(Sandbox): ...
```

## Config

The implementation is constructed with the `sandbox` interface's `SandboxConfig` (see Interface LLS Data Types). It bundles no imported capabilities.

**HLS Justification:** Configured with file mappings, readable/writable paths, blame targets, and limits (per the `sandbox` interface contract).

## Behavioral Description

The `SandboxImpl` class implements the `Sandbox` Protocol, providing all operations: `get_tool_definitions`, `read_file`, `write_file`, `edit_file`, `replace_lines`, `search_files`, `read_chunks`, `replace_chunks`, `verify`, `succeed`, `fail`, `blame`, and `get_write_occurred`.

The implementation:
- Maintains per-run state: the write-occurred flag and per-run stubbing state (region overlap, chunk overlap, and search dedup records); nothing persists across runs. The stubbing state is recoverable from the run's conversation (the tool calls and results), and the conversation is itself per-run state.
- Resolves virtual names to full filesystem paths using `file_mappings`
- Enforces policy by checking virtual paths against `readable_paths` and `writable_paths`
- Applies read size and search result limits
- Uses the filesystem for all read/write operations
- Delegates verification to the injected `verification_callback` when non-null. The callback may perform arbitrary actions (including running shell commands) but must not depend on external state or modify the sandbox's filesystem; guaranteeing this is the assembler's responsibility.
- Conditionally includes tools based on configuration (chunk tools, blame). The verify tool is always emitted.
- Provides `edit_file` (content-based search-and-replace: one occurrence, or all when `expect_multiple` is set) and `replace_lines` (line-range replace, delete, or insert) as file writes: each sets the write-occurred flag, records the changed file, clears per-file stubbing state, and returns a minimal structured result (no file-content echo). `edit_file` rejects identical `old_str`/`new_str` (a no-op edit) as an invalid argument.
- `write_file` creates new files only: it fails when the file already exists, advising `edit_file` or `replace_lines` for modifications.
- `edit_file` and `replace_lines` fail cleanly when the file does not exist, advising `write_file` for creation.
- `read_file` returns lines by 1-indexed line range, prefixed with line numbers (`"N \u2502 line"`) only when `include_line_numbers` is set (default: off) and the file is writable, with a note reporting the next `start_line`; numbered reads record their range as visible for line edits and always provide content. Line-number mode is sticky: a plain read after any numbered read of the same file is a tool failure, ever.
- `replace_lines` may edit only line ranges currently visible in context (numbered reads since the last write; any write clears visibility); otherwise it fails advising a numbered read of the range.
- Processes operations sequentially
- `replace_chunks` operations are atomic (all modifications apply or none do)
- Captures each file's content at run start on its first write of the run; `verify` with no callback diffs the run's changed files against those snapshots and states that no verification tool is present. `verify` with a callback runs the callback and reports its output and success flag.
- Provides error messages that identify the violated policy (policy violations are handled by the sandbox). Messages name the virtual path, never the resolved filesystem path, and list the readable/writable paths.
- Leaves filesystem unchanged on handled errors (policy violations). Filesystem errors and verification-callback exceptions are outside the interface contract; this implementation reports them as tool failures identifying the failing operation.
- Does not persist state across runs
- Sets `stub_previous` according to stubbing semantics in the `sandbox` interface; never produces the stub text itself (previous results are replaced in the conversation by the agent loop, which pins the text)
- `verify` always returns the diff of the run's changed files vs. their run-start snapshots, truncated when it exceeds the diff size limit (default 1000 chars) with a footer reporting the truncated size and full change counts; with a callback it additionally returns the callback's output and success flag followed by succeed() guidance (may be called when passed; when failed, change files and re-verify, or blame/fail to end the run), and with no callback it states that no verification tool is present and that succeed() may now be called
- `blame` with no configured blame targets returns `ToolFailure[str]` (a precondition violation; the tool is not offered when targets are empty)
- Forms the `TerminateAgentWithSuccess` result using `dag_clean_logic` result types:
  - `succeed` — carries `NoChangeResult()` if the write-occurred flag is unset, or `ChangeResult(["Task completed successfully"])` if the run modified the workspace; rejects a change summary for a file whose content equals its run-start snapshot (the claimed change does not appear in the diff)
  - `blame` (valid pairs) — carries `FeedbackResult(messages=blames)` (each pair is one (target, feedback) message)

**HLS Justification:** Uses the filesystem directly and delegates verification when configured.

## Invariants

- No state persists between runs
- Write-occurred flag set immediately upon successful write and never cleared
- Pre-write snapshots are captured before the run's first write of each file and reset each run
- All file operations use resolved filesystem paths, not virtual names
- Chunk operations operate only on Python files
- Verification callback has no filesystem side effects
- All policy checks occur before any filesystem mutation
- Errors leave the filesystem unchanged
- Stubbing state cleared at start of each run


## Non-Concerns

- **Stub text:** The text replacing previous results in the conversation is pinned to `"Content removed because newer version is available"` by the agent loop (not the sandbox); the sandbox only signals stubbing via `stub_previous` and never produces the text itself.
- **Chunking algorithm:** The definition of semantic chunks for `read_chunks`/`replace_chunks` is unspecified.
- **T_tool resolution:** The implementation resolves `T_tool` (from `tool_provider`) to `str` in failure signals (`ToolFailure[str]`).
