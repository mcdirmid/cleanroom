# sandbox_impl

fulfills: sandbox
imports: tool_provider (tool results, signals), dag_clean_logic (termination-result types)
terms (from sandbox): virtual name, file write, blame, blame target
terms (from agent_loop): run
terms (from tool_provider): tool failure

## Deltas beyond the sandbox contract

### Behavior

- Uses the filesystem directly for all operations; verification is delegated to the injected callback when provided.
- Provides the following tools, each as a fixed function: file operations (reading, writing, searching); Python chunk operations (reading and replacing semantic chunks); verification (running the injected callback); termination (success, failure, blame).
- Tools are conditionally included: chunking tools only if Python files are accessible; the verification tool only if the verification callback is non-null; the blame tool only if blame targets are non-empty.

### Ordering

- Tool calls are processed sequentially; the write-occurred flag is set immediately upon a successful write.

### Operation Boundaries

- Chunk-replacement operations apply all modifications or none, per the sandbox contract.

### State Management

- Per-run state only: the write-occurred flag, the run configuration, and per-run stubbing state; nothing persists across runs.

### External Dependencies

- The filesystem and the injected verification callback.

### Error Handling

- Errors are categorized as policy violations, validation errors, filesystem errors, or callback errors.
- Policy violations and validation errors signal failure, leaving the filesystem unchanged; filesystem and callback errors are unhandled.
- Invoking the verification tool with no verification callback, or the blame tool with no configured blame targets, signals a tool failure (the tools are not offered when their preconditions are unmet).

## Non-concerns

- Chunk reading mechanism: the exact method for reading chunks is unspecified.
