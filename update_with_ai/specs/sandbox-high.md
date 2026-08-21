# sandbox

imports: tool_provider (tool definitions, results, signals, stubbing), agent_loop (run), dag_storage (dependency), dag_clean_logic (change message, feedback message)
terms (from tool_provider): tool definition, tool result, supersession flag, stub, termination result, tool failure
terms (from agent_loop): run
terms (from dag_storage): dependency
terms (from dag_clean_logic): change message, feedback message
terms (owned): virtual name, file write, line-numbered view, blame, blame target, soft length bound, hard length bound

## Purpose

Provides a controlled environment for agents to read, write, search, and modify files within a virtual workspace: reading, writing, content-based editing, line-range editing, recursive searching, verification, and termination tools. Enforces per-run policies and signals termination when the agent completes its task.

## Terms

- Virtual name: the name the agent uses to refer to a file; the sandbox resolves it to a full filesystem path.
- File write: any successful operation that modifies the filesystem.
- Line-numbered view: a rendering of a file's content with each line prefixed by its 1-indexed line number; the line numbers are metadata, never file content.
- Blame: a termination outcome that attributes the task's incompleteness to one or more dependencies and provides feedback on how to correct their outputs; blame is not failure.
- Blame target: a dependency the agent may blame.
- Soft length bound: the preferred maximum length of a change summary; a summary exceeding it is rejected with shortening guidance up to a grace count, then accepted when within the hard length bound.
- Hard length bound: the maximum length a change summary may reach; a summary exceeding it is rejected with hard-bound guidance up to a grace count, and a summary still exceeding it after the grace count fails the run (success turns into failure).

## Contract

**Inputs**

- Configured: file mappings (virtual name to full path); readable and writable virtual paths; blame targets (may be empty); the search result limit (the maximum matches a single search may render) and the diff size limit (the maximum characters a verification diff may report); an optional verification callback.
- Per call: a tool call (tool name and arguments, per tool_provider).

**Operations**

- Request tool definitions (per tool_provider).
- Execute a tool call.
- Query whether the run has modified the filesystem.

**Guarantees**

- Permissions are enforced for all operations; file writes are tracked.
- Signals whether any file write has occurred during the run.
- The run begins when the sandbox is configured and ends when the agent signals termination.
- A read provides the file's entire content; reads are not paginated and are not bounded by a size limit.
- Search results beyond the search result limit signal a tool failure advising offset/limit pagination; the limit bounds rendered matches only.
- Search results render matches only for files that are not writable; matches in writable files are reported as counts without content.
- Each tool call produces exactly one outcome: a tool result, continue, terminate with success, terminate with failure, or tool failure.
- Tool results contain the content, the supersession flag, and the note, per tool_provider.
- An edit's replacement applies atomically (all or nothing).
- Error messages identify the violated policy or the failing operation; errors leave the filesystem unchanged.
- A tool failure (invalid arguments, a policy violation, or a termination tool invoked incorrectly) signals failure, leaving the session active.

**Assumptions**

- The agent loop handles free-text responses, routes termination signals, and stubs the earlier result when a result's flag is set, identifying it by the file's virtual name or the verification command.
- The verification callback, if provided, has no side effects on the sandbox's filesystem.

**File operations**

- Writing: new files only; fails when the file already exists; empty content rejected.
- Content-based editing: search-and-replace of short text, bounded in length; longer changes go through line-range editing.
- Line-range editing: replace, delete, insert.
- Recursive searching within a specified path.

**Views**

- A read of a non-writable file renders plain; a read of a writable file renders the line-numbered view only — a plain read of an existing writable file is rejected.
- A file's view is plain until the agent reads the file in the line-numbered view; a read sets the file's view — plain or line-numbered — for the run; a write resets the file's view to plain, invalidating the line numbers (a numbered read re-enables them).
- Line-range edits may target any 1-indexed line range within the file's current bounds, and require the line-numbered view — a write invalidates the line numbers, so a line-range edit after a write requires a fresh numbered read.
- A line-range edit attempted without the line-numbered view signals a tool failure advising a numbered read; the file is left unchanged.
- A read renders the file's content in the file's current view; a write or edit renders the operation's status, never a file-content echo; verification renders the diff report.
- The file's content in the conversation is the content of its most recent non-stubbed result; after a write or edit the file's current content is not visible until the agent reads the file again.

**Stubbing**

- The supersession flag is set on the results of operations on writable files and on verification results; it is not set on reads of files that are not writable, on searches, or on termination results.
- A read of a writable file sets the flag: it supersedes the earlier result for that file.
- A write, a content-based edit, and a line-range edit set the flag: they supersede the earlier result for that file.
- A verification sets the flag: it supersedes the earlier verification result.
- The superseded result is identified by the file's virtual name or the verification command — the name the operation itself carries; no separate identity is introduced.

**Verification**

- Verification is always offered; it reports the diff of the run's file changes (truncated when it exceeds the diff size limit, reporting the truncated size and the full change counts) and, when a verification callback is configured, delegates validation to it, otherwise stating that no verification tool is present.
- The verification result states whether the success termination tool may now be called: after a passing callback or a no-callback verify, success is permitted; after a failing callback, the agent must change files to fix the reported issues and verify again, or call blame or fail to end the run — never re-verify without changes.
- The success termination tool signals termination only after verify has been called when the run changed files (a file write occurred); when a verification callback is configured, it signals termination only after verify has been called and passed (exit 0). An unmet gate signals a tool failure advising the agent to verify (fixing any issues) or to call fail or blame to end the run. Termination failure tools are never gated.

**Termination**

- Termination tools: success, failure, and blame. The success operation and a valid blame signal successful termination; the failure operation ends the session in failure. Termination tools signal termination when invoked correctly.
- Blame is offered only when blame targets are configured; each (target, feedback) pair is delivered as a feedback message to the blamed node, which is re-cleaned so the blaming node can run again.
- Termination is at the agent's judgment: the agent signals termination when it considers its task complete, or when it cannot be completed.
- The success termination tool carries the agent's change summary — naming the parts of each changed file that changed, so the next reader knows what to pay attention to when updating further artifacts (not the task performed, not how it was done) — broadcast to reverse dependencies to bring the next agent's attention to the changes; when the run changed files, a missing, malformed, or incomplete summary signals a tool failure that lists the changed files and the required shape.
- Change summaries are bounded by a soft length bound and a hard length bound: a summary within the soft bound is accepted; a summary exceeding the soft bound but within the hard bound is rejected with guidance up to a number of attempts and then accepted; a summary exceeding the hard bound is rejected with guidance up to a number of attempts and then fails the run (success turns into failure).

## Non-concerns

- Error message wording: error messages identify the violated policy or failing operation; their exact wording is unspecified.
