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

The `SandboxImpl` class implements the `Sandbox` Protocol, providing all operations: `get_tool_definitions`, `read_file`, `write_file`, `search_files`, `read_chunks`, `replace_chunks`, `verify`, `succeed`, `fail`, `blame`, and `get_write_occurred`.

The implementation:
- Maintains per-run state: the write-occurred flag and per-run stubbing state (region overlap, chunk overlap, and search dedup records); nothing persists across runs. The stubbing state is recoverable from the run's conversation (the tool calls and results), and the conversation is itself per-run state.
- Resolves virtual names to full filesystem paths using `file_mappings`
- Enforces policy by checking virtual paths against `readable_paths` and `writable_paths`
- Applies read size and search result limits
- Uses the filesystem for all read/write operations
- Delegates verification to the injected `verification_callback` when non-null. The callback may perform arbitrary actions (including running shell commands) but must not depend on external state or modify the sandbox's filesystem; guaranteeing this is the assembler's responsibility.
- Conditionally includes tools based on configuration (chunk tools, verify, blame). The verify tool is emitted only when a non-null `verification_callback` is set in `SandboxConfig`.
- Processes operations sequentially
- `replace_chunks` operations are atomic (all modifications apply or none do)
- Provides error messages that identify the violated policy (policy violations are handled by the sandbox). Messages name the virtual path, never the resolved filesystem path, and list the readable/writable paths.
- Leaves filesystem unchanged on handled errors (policy violations). Filesystem errors and verification-callback exceptions are outside the interface contract; this implementation reports them as tool failures identifying the failing operation.
- Does not persist state across runs
- Sets `stub_previous` according to stubbing semantics in the `sandbox` interface
- Uses stub replacement text: `"Content removed because newer version is available"`
- `verify` with a null callback returns `ToolFailure[str]` (a precondition violation; the tool is not offered when the callback is null)
- `blame` with no configured blame targets returns `ToolFailure[str]` (a precondition violation; the tool is not offered when targets are empty)
- Forms the `TerminateAgentWithSuccess` result using `dag_clean_logic` result types:
  - `succeed` — carries `NoChangeResult()` if the write-occurred flag is unset, or `ChangeResult(["Task completed successfully"])` if the run modified the workspace
  - `blame` (valid pairs) — carries `FeedbackResult(messages=blames)` (each pair is one (target, feedback) message)

**HLS Justification:** Uses the filesystem directly and delegates verification when configured.

## Invariants

- No state persists between runs
- Write-occurred flag set immediately upon successful write and never cleared
- All file operations use resolved filesystem paths, not virtual names
- Chunk operations operate only on Python files
- Verification callback has no filesystem side effects
- All policy checks occur before any filesystem mutation
- Errors leave the filesystem unchanged
- Stubbing state cleared at start of each run


## Non-Concerns

- **Stub replacement text:** Pinned to `"Content removed because newer version is available"` in this implementation (the interface leaves the exact text unspecified).
- **Chunking algorithm:** The definition of semantic chunks for `read_chunks`/`replace_chunks` is unspecified.
- **T_tool resolution:** The implementation resolves `T_tool` (from `tool_provider`) to `str` in failure signals (`ToolFailure[str]`).
