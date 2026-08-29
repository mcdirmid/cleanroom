# run_control_impl

fulfills: run_control
imports: tool_provider (tool results, signals), dag_clean_logic (change message, feedback message, termination-result types), dag_storage (node message), file_reader (virtual name)
terms (from tool_provider): tool failure, supersession flag
terms (from dag_clean_logic): change message
terms (from file_reader): virtual name
terms (from run_control): blame, blame target, soft length bound, hard length bound
terms (refined): blame target

## Deltas

- [refines] blame target -> the virtual name of the blamed artifact; the implementation resolves the virtual name to the owning node via the configured blame targets mapping before forming the feedback result.
- Verification is delegated to the injected callback when provided.
- Advance performs the session's verification internally: it computes the diff of the session's changes, truncated when it exceeds the diff size limit (reporting the truncated size and the full change counts) and, when configured, runs the injected verification callback; on a failing verification it provides feedback (never a tool failure) and the session continues; a failing verification's feedback does not include the diff and sanitizes referenced paths to virtual names through file_reader.
- Change summaries are bounded by the soft length bound and the hard length bound: advance rejects a change message over the soft bound with shortening guidance up to a grace count, then accepts it when within the hard bound; a change message still over the hard bound after the grace count fails the session (advance turns into failure). The bound values are pinned in the implementation LLS.
- A missing or out-of-bounds change message signals a tool failure that lists the changed files and shows the session's diff.
- Sets the supersession flag on verification results, never on termination results.
- [ordering] Advance's feedback on a failing verification supersedes the earlier verification result.
- [ordering] The feedback-pending gate is checked only when advance would otherwise signal successful termination without a change; a failing verification and the change-message requirement are checked first.
- [state] Per-run state only: the diff and the verification outcome; nothing persists across runs.
- [external] The injected verification callback and the diff size limit (the maximum characters a verification diff may report).
- [failure] Callback errors are unhandled.

## Non-concerns

- Diff presentation: the exact rendering of the verification diff and its truncation report is unspecified.
