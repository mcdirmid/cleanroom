# sandbox_impl

fulfills: sandbox
imports: tool_provider (tool results, signals), dag_clean_logic (termination-result types)
terms (from sandbox): virtual name, file write, line-numbered view, injected read, session-start read, blame, blame target, soft length bound, hard length bound, template, guide, guide summary, step section, step mode
terms (from agent_loop): run
terms (from dag_clean_logic): change message
terms (from tool_provider): tool failure, supersession flag, stub
terms (refined): virtual name

## Deltas

- [refines] virtual name -> the implementation addresses every configured file by its virtual name — the file's final path component, or the shortest path suffix unique among the configured files — and never presents a file's full path to the agent: reads, writes, edits, searches, session-start reads, and error messages name files by virtual name.
- [refines] blame target -> the virtual name of the blamed artifact; the implementation resolves the virtual name to the owning node via the configured blame targets mapping before forming the feedback result.
- Uses the filesystem directly for all operations; verification is delegated to the injected callback when provided.
- Provides the following tools, each as a fixed function: file operations (reading the entire file, writing, content-based editing, line-range editing, searching); termination (advance, failure, blame).
- Tools are conditionally included: the blame tool only if blame targets are non-empty. The advance tool is always included.
- Advance performs the run's verification internally: it computes the diff of the run's changes (truncated when it exceeds the diff size limit, reporting the truncated size and the full change counts) and, when configured, runs the injected verification callback; on a failing verification it provides feedback (never a tool failure) and the session continues; a failing verification's feedback does not include the diff; on a passing verification it requires the change message when files changed and signals successful termination (per the termination-result types); a missing or out-of-bounds change message signals a tool failure that lists the changed files and shows the run's diff.
- In step mode, the step-section pointer gates advance's outputs between the next step section, the restated guide summary, and the termination machinery, per the interface's Step mode rules.
- Sets the supersession flag on the results of operations on writable files and on verification results, never on reads of files that are not writable, on searches, or on termination results.
- A read of a writable file supersedes the earlier result for that file; a write, a content-based edit, and a line-range edit supersede the earlier result for that file; each advance output supersedes the earlier advance output (in step mode, the previous step-mode output); advance's feedback on a failing verification supersedes the earlier verification result.
- The superseded result is identified by the file's virtual name or the advance operation.
- A successful write, content-based edit, or line-range edit provides a write confirmation and an injected read (a numbered read of the file); the agent loop applies the stubbing.
- The write confirmation's content is the operation's status, never a file-content echo.
- [state] Supersession is matched by the file's virtual name or the advance operation; no separate identity is introduced.
- Provides the session-start reads: when enabled, a plain read (never superseding) of every configured file that is readable but not writable and exists as a regular file on disk, sorted by virtual name; in step mode, the guide is not among them.
- Reads the declared guide's content at run start and splits it into its guide summary and step sections, following the guide format; the guide's content is available only through the step-delivery rules.
- In step mode, excludes the guide from the run's readable files: reads of the guide are rejected and the guide is never provided whole.
- Pre-injects the advance call providing the step-mode output (the guide summary and the ensure instruction) as a presented result at run start, before the agent's first turn.
- Maintains the step-section pointer: a passing verification advances it; a failing verification does not; the pointer gates which output the advance tool provides.
- [ordering] In step mode, each advance output is composed at delivery time from the guide summary, the ensure instruction, and the pointer's current selection (a step section or the failure reason), per the interface's Step mode rules.
- Provides the advance tool's definition without the change-message argument while step sections remain; when verification passes with no step sections remaining, the definition includes it.
- [ordering] A writable file with a configured template that does not exist on disk is created when the sandbox is configured, before any tool call.
- [state] A file initialized from its template is run-start state: its pre-write snapshot is the template's content.
- Change summaries are written for the next reader: the injected read makes the changed file's content visible in the conversation immediately after the write.
- Change summaries are bounded by the sandbox's soft and hard length bounds: `advance` rejects a change message over the soft bound with shortening guidance up to a grace count, then accepts it when within the hard bound; a change message still over the hard bound after the grace count fails the run (advance turns into failure). The bound values are pinned in the implementation LLS.
- [ordering] Tool calls are processed sequentially; the write-occurred flag is set immediately upon a successful write.
- [ordering] The injected read follows the write confirmation immediately; both precede the results of any subsequent tool call.
- [state] Per-run state only: the write-occurred flag, the run configuration, the per-file view modes, the pre-write snapshots, and the step state (the guide, its split, and the step-section pointer); nothing persists across runs. No stubbing state is maintained.
- [state] The injected read renders the file's post-write content in the line-numbered view, restoring the file's line-numbered view state; no additional per-run state is required.
- [state] A read sets the file's view — plain or line-numbered — for the run; a write resets the view to plain, invalidating the line numbers, and the injected read that follows re-enables the line-numbered view.
- [external] The filesystem, the injected verification callback, and the diff size limit (the maximum characters a verification diff may report).
- [failure] Errors are categorized as policy violations, validation errors, filesystem errors, or callback errors.
- [failure] Policy violations and validation errors signal failure, leaving the filesystem unchanged; filesystem and callback errors are unhandled.
- [failure] A write that fails provides no injected read.

## Non-concerns

- View handling: the exact mechanism for tracking per-file view modes is unspecified.
