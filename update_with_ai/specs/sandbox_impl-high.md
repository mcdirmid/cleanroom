# sandbox_impl

fulfills: sandbox
imports: tool_provider (tool results, signals), dag_clean_logic (termination-result types)
terms (from sandbox): virtual name, file write, line-numbered view, injected read, session-start read, blame, blame target, soft length bound, hard length bound, template
terms (from agent_loop): run
terms (from dag_clean_logic): change message
terms (from tool_provider): tool failure, supersession flag, stub

## Deltas

- Uses the filesystem directly for all operations; verification is delegated to the injected callback when provided.
- Provides the following tools, each as a fixed function: file operations (reading the entire file, writing, content-based editing, line-range editing, searching); termination (advance, failure, blame).
- Tools are conditionally included: the blame tool only if blame targets are non-empty. The advance tool is always included.
- Advance performs the run's verification internally: it computes the diff of the run's changes and, when configured, runs the injected verification callback; on a failing verification it provides feedback (never a tool failure) and the session continues; on a passing verification it requires the change message when files changed and signals successful termination (per the termination-result types); a missing or out-of-bounds change message signals a tool failure that lists the changed files and shows the run's diff.
- Sets the supersession flag per the interface's stubbing rules; a successful write, content-based edit, or line-range edit provides a write confirmation and an injected read (a numbered read of the file); the agent loop applies the stubbing.
- Provides the session-start reads: when enabled, a plain read (never superseding) of every configured file that is readable but not writable and exists as a regular file on disk, sorted by virtual name.
- [ordering] A writable file with a configured template that does not exist on disk is created when the sandbox is configured, before any tool call.
- [state] A file initialized from its template is run-start state: its pre-write snapshot is the template's content.
- Change summaries are written for the next reader: the injected read makes the changed file's content visible in the conversation immediately after the write; the summary names the parts of the file that changed, directing the reader's attention there.
- Change summaries are bounded by the sandbox's soft and hard length bounds: `advance` rejects a change message over the soft bound with shortening guidance up to a grace count, then accepts it when within the hard bound; a change message still over the hard bound after the grace count fails the run (advance turns into failure). The bound values are pinned in the implementation LLS.
- [ordering] Tool calls are processed sequentially; the write-occurred flag is set immediately upon a successful write.
- [ordering] The injected read follows the write confirmation immediately; both precede the results of any subsequent tool call.
- [state] Per-run state only: the write-occurred flag, the run configuration, the per-file view modes, and the pre-write snapshots; nothing persists across runs. No stubbing state is maintained.
- [state] The injected read renders the file's post-write content in the line-numbered view, restoring the file's line-numbered view state; no additional per-run state is required.
- [external] The filesystem and the injected verification callback.
- [failure] Errors are categorized as policy violations, validation errors, filesystem errors, or callback errors.
- [failure] Policy violations and validation errors signal failure, leaving the filesystem unchanged; filesystem and callback errors are unhandled.
- [failure] A write that fails provides no injected read.

## Non-concerns

- View handling: the exact mechanism for tracking per-file view modes is unspecified.
