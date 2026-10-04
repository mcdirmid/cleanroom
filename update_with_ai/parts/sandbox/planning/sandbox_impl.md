# sandbox_impl implementation component

imports: sandbox_file_editor
implements: sandbox

## Intent

Agent sessions require guaranteed workspace state before tool execution begins and accurate tracking of resulting file modifications. The sandbox_impl implementation component bridges the sandbox boundary to the peer edit manager, delegating starter template materialization and exposing session-wide file modification state.

By delegating template materialization to write missing read-write files while preserving existing files and querying modification state from the edit manager, the implementation maintains consistent session state without duplicating editor logic.

## Factored Contracts

### Contracts

- Querying file modifications delegates to the edit manager. [delegate_file_modifications]
- Materializing startup templates delegates to the edit manager. [delegate_template_materialization]
- Materializing startup templates writes template content to missing read-write files. [write_template_to_missing_files]
- Materializing startup templates preserves existing files without overwriting. [preserve_existing_files_on_materialization]

## Woven Contracts

- Querying session modifications retrieves modification state from the edit manager. [delegate_file_modifications, sandbox: [expose_modifications_occurred], sandbox_file_editor: [writes_occurred_true_on_diff, writes_occurred_false_on_match]]
- Materializing startup templates invokes edit manager template materialization to write missing files while preserving existing content. [delegate_template_materialization, write_template_to_missing_files, preserve_existing_files_on_materialization, sandbox: [materialize_startup_templates, preserve_existing_files_during_materialization], sandbox_file_editor: [materialize_templates_at_start]]
