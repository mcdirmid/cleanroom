# sandbox

imports: tool_provider (tool definitions, results, signals, stubbing)
terms (from tool_provider): tool definition, tool result, content ID, stub, termination result, tool failure
terms (from agent_loop): run
terms (from dag_storage): dependency
terms (from dag_clean_logic): change message, feedback message
terms (owned): virtual name, file write, blame, blame target

## Purpose

Provides a controlled environment for agents to read, write, search, and modify files within a virtual workspace. Enforces per-run policies and signals termination when the agent completes its task.

## Owned definitions

- Virtual name: the name the agent uses to refer to a file; the sandbox resolves it to a full filesystem path.
- File write: any successful operation that modifies the filesystem.
- Blame: a termination outcome that attributes the task's incompleteness to one or more dependencies and provides feedback on how to correct their outputs; blame is not failure.
- Blame target: a dependency the agent may blame.

## Observable dataflow

- Inputs: tool calls (tool name and arguments, per tool_provider).
- Outputs: tool definitions in the tool_provider format; per call, exactly one outcome — a tool result, continue, terminate with success, terminate with failure, or tool failure.
- The run begins when the sandbox is configured and ends when the agent signals termination; the sandbox exposes whether any file write occurred during the run.
- File operations: reading (line-numbered, by 1-indexed line range), writing (new files only; fails when the file already exists; empty content rejected), content-based editing (search-and-replace), line-range editing (replace, delete, insert), and recursive searching within a specified path. A read with an omitted end line covers the whole remaining file; a read whose content would exceed the read size limit signals a tool failure advising a smaller line range. Line-numbered reads are allowed only for writable files and are sticky: once a file is read with line numbers, plain reads of it fail (a tool failure, ever). Line-range edits may target only ranges currently visible in context (numbered reads since the file's last write; any write clears what is visible). Search results beyond the search result limit signal a tool failure advising offset/limit pagination. Write and edit results are minimal: a structured success message with counts, never a file-content echo.
- Chunk operations read and replace semantic chunks of Python source files; offered only when Python source files are accessible; a chunk read may include adjacent chunks for context when requested.
- Verification: always offered; reports the diff of the run's file changes (truncated when it exceeds the diff size limit) and, when a verification callback is configured, delegates validation to it, otherwise stating that no verification tool is present. The verification result states whether `succeed` may now be called: after a passing callback or a no-callback verify, `succeed` is permitted; after a failing callback, the agent must change files to fix the reported issues and verify again, or call `blame`/`fail` to end the run — never re-verify without changes.
- Termination tools: success, failure, and blame. Success and a valid blame signal successful termination; the failure operation ends the session in failure. Blame is offered only when blame targets are configured; each (target, feedback) pair is delivered as a feedback message to the blamed node, which is re-cleaned so the blaming node can run again.
- The sandbox does not prevent the agent from ending a turn without calling an end-run tool; the agent loop handles detection of free-text responses.
- Termination is at the agent's judgment: the agent signals termination when it considers its task complete, or when it cannot be completed.

### Deduplication

- The content ID identifies the file or tool operated on: the virtual file path for filesystem operations; the verification tool itself for verification; none for termination tools.
- A file read signals stubbing when the read region overlaps previously read content for the same file that has not been stubbed; the read itself always provides the requested content, and the overlap stubs the previous instances.
- A chunk read signals stubbing when the chunks it provides (requested plus adjacent context) overlap previously read chunks for the same file that have not been stubbed; the chunk read itself always provides the requested chunk content.
- A file search signals stubbing when the same pattern and path were previously searched.
- A file write signals stubbing unconditionally: it stubs all previous content for that file and clears per-file stubbing state (read regions, chunk indices, search dedup records), so subsequent reads are not stubbed based on pre-write reads; the write result is minimal (no file content).
- A chunk replacement signals stubbing unconditionally, with the same effect as a file write.
- A verification signals stubbing unconditionally, stubbing all previous verification results.
- Termination tools never signal stubbing; results with no content ID are never stubbed; stubbing preserves the original position of messages in the conversation.

## Contract

**The client configures the component with:**

- File mappings (virtual name to full path).
- Readable and writable virtual paths.
- Blame targets (may be empty).
- The read size limit (the maximum content a single read may return), the search result limit (the maximum matches a single search may return), and the diff size limit (the maximum characters a verification diff may report).
- An optional verification callback.

**The client may:**

- Request tool definitions (per tool_provider).
- Execute a tool call.
- Query whether the run has modified the filesystem.

**The component guarantees:**

- Permissions are enforced for all operations; file writes are tracked.
- Signals whether any file write has occurred during the run.
- Reads are bounded: an omitted limit reads the whole remaining file, and a read (file or chunk) whose content would exceed the read size limit signals a tool failure advising pagination, as does an explicit limit above the read size limit. Search results beyond the search result limit signal a tool failure advising offset/limit pagination.
- Verification diffs are bounded: a diff exceeding the diff size limit is truncated, reporting the truncated size and the full change counts.
- Every successful file read, chunk read, and search carries a note reporting how much content remains and how to continue reading.
- The success termination tool signals termination only after verify() has been called when the run changed files (a file write occurred); when a verification callback is configured, it signals termination only after verify() has been called and passed (exit 0). An unmet gate signals a tool failure advising the agent to verify (fixing any issues) or to call fail() or blame() to end the run. Termination failure tools are never gated.
- The success termination tool carries the agent's change summary — one short sentence per changed file on what changed (not how it was done) — broadcast to reverse dependencies to bring the next agent's attention to the changes; when the run changed files, a missing, malformed, over-long, or incomplete summary signals a tool failure that lists the changed files and the required shape.
- Termination tools signal termination when invoked correctly: the success operation and a valid blame signal successful termination; the failure operation ends the session in failure.
- A tool failure (invalid arguments, a policy violation, or a termination tool invoked incorrectly) signals failure, leaving the session active.
- Each tool call produces exactly one outcome: a tool result, continue, terminate with success, terminate with failure, or tool failure.
- Tool results contain the content, a content ID, and a stub flag, per tool_provider.
- All modifications of a chunk replacement apply atomically (all or nothing).
- Error messages identify the violated policy or the failing operation; errors leave the filesystem unchanged.

**The component assumes:**

- The agent loop handles free-text responses, routes termination signals, and maintains the mapping between content IDs and results for stubbing.
- The verification callback, if provided, has no side effects on the sandbox's filesystem.

## Non-concerns

- Error message wording: error messages identify the violated policy or failing operation; their exact wording is unspecified.
