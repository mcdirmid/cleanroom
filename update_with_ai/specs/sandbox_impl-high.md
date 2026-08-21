# sandbox_impl

fulfills: sandbox
imports: tool_provider (tool results, signals), dag_clean_logic (termination-result types)
terms (from sandbox): virtual name, file write, line-numbered view, blame, blame target, soft length bound, hard length bound
terms (from agent_loop): run
terms (from tool_provider): tool failure, supersession flag, stub

## Deltas

- Uses the filesystem directly for all operations; verification is delegated to the injected callback when provided.
- Provides the following tools, each as a fixed function: file operations (reading the entire file, writing, content-based editing, line-range editing, searching); verification (reporting the diff of the run's changes and, when configured, running the injected callback); termination (success, failure, blame).
- Tools are conditionally included: the blame tool only if blame targets are non-empty. The verification tool is always included.
- Sets the supersession flag on each result; the agent loop applies the stubbing.
- Change summaries are written for the next reader: a write or edit supersedes the file's earlier results, so the changed file's content is not visible until the agent reads it again; the summary names the parts of the file that changed, directing the reader's attention there.
- Change summaries are bounded by the sandbox's soft and hard length bounds: `succeed` rejects a summary over the soft bound with shortening guidance up to a grace count, then accepts it when within the hard bound; a summary still over the hard bound after the grace count fails the run (success turns into failure). The bound values are pinned in the implementation LLS.
- [ordering] Tool calls are processed sequentially; the write-occurred flag is set immediately upon a successful write.
- [state] Per-run state only: the write-occurred flag, the run configuration, the per-file view modes, and the pre-write snapshots; nothing persists across runs. No stubbing state is maintained.
- [external] The filesystem and the injected verification callback.
- [failure] Errors are categorized as policy violations, validation errors, filesystem errors, or callback errors.
- [failure] Policy violations and validation errors signal failure, leaving the filesystem unchanged; filesystem and callback errors are unhandled.

## Non-concerns

- View handling: the exact mechanism for tracking per-file view modes is unspecified.
