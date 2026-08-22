# sandbox

imports: tool_provider (tool definitions, results, signals, stubbing), agent_loop (run), dag_storage (dependency), dag_clean_logic (change message, feedback message)
terms (from tool_provider): tool definition, tool result, supersession flag, stub, termination result, tool failure
terms (from agent_loop): run
terms (from dag_storage): dependency
terms (from dag_clean_logic): change message, feedback message
terms (owned): virtual name, file write, line-numbered view, injected read, session-start read, blame, blame target, soft length bound, hard length bound

## Purpose

Provides a controlled environment for agents to read, write, search, and modify files within a virtual workspace: reading, writing, content-based editing, line-range editing, recursive searching, verification, and termination tools. Enforces per-run policies and signals termination when the agent completes its task.

## Terms

- Virtual name: the name the agent uses to refer to a file; the sandbox resolves it to a full filesystem path.
- File write: any successful operation that modifies the filesystem.
- Line-numbered view: a rendering of a file's content with each line prefixed by its 1-indexed line number; the line numbers are metadata, never file content.
- Injected read: the read provided for a file immediately after a successful file write of that file, presenting a read request with line numbers and the read result carrying the file's full current content; the agent did not request it, and to the agent it appears as a numbered read it requested.
- Session-start read: a read of a file the agent can read but not write, provided at the beginning of a run for rendering before the agent's first turn; it renders the file's content plain, never supersedes an earlier result, and is never stubbed.
- Blame: a termination outcome that attributes the task's incompleteness to one or more dependencies and provides feedback on how to correct their outputs; blame is not failure.
- Blame target: a dependency the agent may blame.
- Soft length bound: the preferred maximum length of a change summary; a summary exceeding it is rejected with shortening guidance up to a grace count, then accepted when within the hard length bound.
- Hard length bound: the maximum length a change summary may reach; a summary exceeding it is rejected with hard-bound guidance up to a grace count, and a summary still exceeding it after the grace count fails the run (success turns into failure).

## Contract

**Inputs**

- Configured: file mappings (virtual name to full path); readable and writable virtual paths; blame targets (may be empty); the search result limit (the maximum matches a single search may render) and the diff size limit (the maximum characters a verification diff may report); whether session-start reads are enabled; an optional verification callback.
- Per call: a tool call (tool name and arguments, per tool_provider).

**Operations**

- Request tool definitions (per tool_provider).
- Execute a tool call.
- Query whether the run has modified the filesystem.
- Request the session-start reads.

**Guarantees**

- Permissions are enforced for all operations; file writes are tracked.
- Signals whether any file write has occurred during the run.
- The run begins when the sandbox is configured and ends when the agent signals termination.
- A read provides the file's entire content; reads are not paginated and are not bounded by a size limit.
- Search results beyond the search result limit signal a tool failure advising offset/limit pagination; the limit bounds rendered matches only.
- Search results render matches only for files that are not writable; matches in writable files are reported as counts without content.
- Each tool call produces exactly one outcome: one or more tool results, or a signal — continue, terminate with success, terminate with failure, or tool failure.
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
- A file's view is plain until a read renders the line-numbered view; a read sets the file's view — plain or line-numbered — for the run; a write resets the file's view to plain, invalidating the line numbers, and the injected read that follows the write re-enables the line-numbered view.
- Line-range edits may target any 1-indexed line range within the file's current bounds, and require the line-numbered view; the injected read after a write provides the line-numbered view, so a line-range edit may follow a write without a further read.
- A line-range edit attempted without the line-numbered view signals a tool failure advising a numbered read; the file is left unchanged.
- A read renders the file's content in the file's current view; a write or edit renders the operation's status, never a file-content echo; verification renders the diff report.
- The file's content in the conversation is the content of its most recent non-stubbed result; after a write or edit the injected read provides the file's current content.

**Stubbing**

- The supersession flag is set on the results of operations on writable files and on verification results; it is not set on reads of files that are not writable, on searches, or on termination results.
- A read of a writable file sets the flag: it supersedes the earlier result for that file.
- A write, a content-based edit, and a line-range edit set the flag: they supersede the earlier result for that file.
- Advance's feedback on a failing verification sets the flag: it supersedes the earlier verification result.
- The superseded result is identified by the file's virtual name or the advance operation — the name the operation itself carries; no separate identity is introduced.

**Auto re-read**

- Every file write provides a write confirmation and an injected read for the written file, in that order.
- The injected read includes a read request for the file with line numbers and the read result, which provides the file's full current content.
- The injected read appears in the conversation immediately after the write confirmation, before any subsequent messages.
- The read result is present in the conversation before the agent's next turn.
- The agent did not request the injected read; to the agent it appears as a numbered read it requested.
- The injected read is a read of a writable file: it supersedes the file's earlier result and is itself superseded by the next write or read for the file, per the Stubbing rules.
- A write that fails provides no injected read.

**Session-start reads**

- When session-start reads are enabled, the session-start reads are the reads of every file that is readable but not writable and exists as a regular file on disk; when disabled, no session-start reads are provided.
- Session-start reads are provided in a deterministic order (sorted by virtual name).
- A session-start read includes a read request for the file and the read result, presented as a read the agent requested.
- A session-start read renders the file's content plain.
- A session-start read does not set the supersession flag.
- A session-start read is never stubbed: no file write targets a file that is not writable, and a read of a file that is not writable never supersedes an earlier result.

**Verification**

- Verification runs automatically as part of the advance operation: advance computes the diff of the run's file changes (truncated when it exceeds the diff size limit, reporting the truncated size and the full change counts) and, when a verification callback is configured, delegates validation to it, otherwise treating verification as passed.
- A failing verification provides feedback — the verification failure details and guidance to change files and call advance again, or call blame or fail to end the run — and the session continues; advance never terminates on a failing verification.
- The run's diff is shown to the agent only as part of the tool failure that requests the change message: when advance's verification passed, the run changed files, and the change message is empty; a failing verification's feedback does not include the diff.

**Termination**

- Termination tools: advance, failure, and blame. Advance verifies the run and then signals successful termination; a valid blame signals successful termination; the failure operation ends the session in failure. Termination tools signal termination when invoked correctly.
- Blame is offered only when blame targets are configured; each (target, feedback) pair is delivered as a feedback message to the blamed node, which is re-cleaned so the blaming node can run again.
- Termination is at the agent's judgment: the agent signals termination when it considers its task complete, or when it cannot be completed.
- Advance signals termination only when its internal verification passes (or no verification callback is configured); when the run changed no files, advance signals successful termination without a change message.
- Advance carries the agent's change summary — naming the parts of each changed file that changed, so the next reader knows what to pay attention to when updating further artifacts (not the task performed, not how it was done) — broadcast to reverse dependencies to bring the next agent's attention to the changes; when the run changed files, a missing, malformed, or incomplete summary signals a tool failure (per the tool failure policy) that lists the changed files and asks for the change message in the required shape.
- Change summaries are bounded by a soft length bound and a hard length bound: a summary within the soft bound is accepted; a summary exceeding the soft bound but within the hard bound is rejected with guidance up to a number of attempts and then accepted; a summary exceeding the hard bound is rejected with guidance up to a number of attempts and then fails the run (advance turns into failure).

## Non-concerns

- Error message wording: error messages identify the violated policy or failing operation; their exact wording is unspecified.
- Session-start read size: session-start reads inherit the unbounded-read rule; the read-only files are assumed to be reasonably sized, so no separate size bound is introduced for session-start reads.
- Advance tool description: the advance tool's description wording is unspecified; the tool's contract is defined by the Verification and Termination rules.
