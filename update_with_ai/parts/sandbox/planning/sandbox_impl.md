<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-05T05:35:22Z
CHANGE: Align purpose with sandbox, add session config template resolution, and fix citations
CODE_HASH: c8dcdcc374a8
-->

# sandbox_impl implementation component

imports: sandbox_file_editor, dag_storage, agent_node_config
implements: sandbox

## Intent

Agent sessions operate across heterogeneous tools spanning file inspection, editing, and outcome control. The sandbox_impl implementation component establishes a unified session coordination boundary that ensures template materialization precedes agent execution, resolving session read-write files and templates from session config, delegating starter template materialization to dag storage, and exposing session-wide file modification state from the edit manager.

By delegating template materialization to dag storage to write missing read-write files while preserving existing files and querying modification state from the edit manager, the implementation maintains consistent session state without duplicating storage logic.

## Factored Contracts

### Contracts

- Querying file modifications delegates to the edit manager. [delegate_file_modifications]
- Materializing startup templates resolves session read-write files and templates from session config. [resolve_read_write_files_and_templates_from_session_config]
- Materializing startup templates delegates to dag storage. [delegate_template_materialization]
- Materializing startup templates writes template content to missing read-write files. [write_template_to_missing_files]
- Materializing startup templates preserves existing files without overwriting. [preserve_existing_files_on_materialization]

## Woven Contracts

- Querying session modifications retrieves modification state from the edit manager. \[delegate_file_modifications, sandbox: [expose_modifications_occurred], sandbox_file_editor: [writes_occurred_true_on_diff, writes_occurred_false_on_match]\]
- Materializing startup templates resolves files and templates from session config and invokes dag storage to write missing files while preserving existing content. \[resolve_read_write_files_and_templates_from_session_config, delegate_template_materialization, write_template_to_missing_files, preserve_existing_files_on_materialization, sandbox: [materialize_startup_templates, preserve_existing_files_during_materialization], agent_node_config: [session_config_read_write_files, session_config_templates], dag_storage: [materialize_node_template]\]
