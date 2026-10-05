<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T02:07:35Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: ef692a292b87
-->

# sandbox_impl implementation component

imports: sandbox_file_editor, dag_storage, agent_node_config
implements: sandbox

## Intent

Agent sessions require guaranteed workspace state before tool execution begins and accurate tracking of resulting file modifications. The sandbox_impl implementation component bridges the sandbox boundary to peer services, delegating starter template materialization to dag storage and exposing session-wide file modification state from the edit manager.

By delegating template materialization to dag storage to write missing read-write files while preserving existing files and querying modification state from the edit manager, the implementation maintains consistent session state without duplicating storage logic.

## Factored Contracts

### Contracts

- Querying file modifications delegates to the edit manager. [delegate_file_modifications]
- Materializing startup templates delegates to dag storage. [delegate_template_materialization]
- Materializing startup templates writes template content to missing read-write files. [write_template_to_missing_files]
- Materializing startup templates preserves existing files without overwriting. [preserve_existing_files_on_materialization]

## Woven Contracts

- Querying session modifications retrieves modification state from the edit manager. \[delegate_file_modifications, sandbox: [expose_modifications_occurred], sandbox_file_editor: [writes_occurred_true_on_diff, writes_occurred_false_on_match]\]
- Materializing startup templates invokes dag storage template materialization to write missing files while preserving existing content. \[delegate_template_materialization, write_template_to_missing_files, preserve_existing_files_on_materialization, sandbox: [materialize_startup_templates, preserve_existing_files_during_materialization], dag_storage: [materialize_template_writes_missing_files, materialize_template_preserves_existing_files]\]
