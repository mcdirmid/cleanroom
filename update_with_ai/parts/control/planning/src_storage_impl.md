<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-08T00:46:00Z
CHANGE: Define src_storage_impl planning specification
CODE_HASH: 4aa416a20035
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# src_storage_impl implementation component

imports: file_paths, src_metadata
implements: agent_storage, dag_storage

## Intent

Coordinating multi-node builds requires fast in-memory access to target metadata alongside durable on-disk persistence of inter-node communication records. Storing inter-node communication records in sidecar package files causes state desynchronization, ghost records, and merge conflicts across branches. The src_storage_impl implementation component resolves declared source files against the workspace root, extracts and updates in-band comment headers, evaluates dirty status dynamically from forward dependency timestamps and unacted feedback, and filters silent dependencies from dirty propagation.

By storing clean status, change summaries, and feedback directly within source files, the implementation provides transparent, self-describing provenance that synchronizes atomically with version control.

## Factored Contracts

### Contracts

- The agent storage maintains node definitions mapped to nodes in dag storage. [maintain_node_definitions]
- The agent storage maintains task prompts mapped to nodes in dag storage. [maintain_task_prompts]
- The agent storage maintains declared source paths mapped to nodes in dag storage. [maintain_source_paths]
- The agent storage maintains forward dependencies mapped to nodes in dag storage. [maintain_forward_dependencies]
- The agent storage maintains feedback dependencies mapped to nodes in dag storage. [maintain_feedback_dependencies]
- The agent storage records declared source file paths for nodes in dag storage. [record_source_file_path]
- The agent storage stores forward dependencies for nodes in dag storage. [store_forward_dependencies]
- The agent storage stores silent source file paths for nodes in dag storage. [store_silent_source_files]
- The agent storage stores feedback dependencies for nodes in dag storage. [store_feedback_dependencies]
- Querying feedback dependencies for an unconfigured auditor node raises an error. [fail_unconfigured_auditor_feedback_dependencies]
- Evaluating dirty status for an unconfigured auditor node raises an error. [fail_unconfigured_auditor_dirty_evaluation]
- An auditor node without configured feedback dependencies evaluates as dirty if any non-silent forward dependency is dirty. [delegate_auditor_dirty_to_dependencies]
- The agent storage resolves declared source paths against the workspace root. [resolve_source_path]
- The agent storage extracts in-band metadata from declared source files. [extract_in_band_metadata]
- A node in dag storage is dirty when its declared source file is missing from the workspace root. [dirty_when_source_missing]
- A node in dag storage records a change message to implement the source file when its source file is missing. [record_change_message_when_source_missing]
- A node in dag storage is dirty when its source file metadata is missing or unparseable. [dirty_when_metadata_invalid]
- A node in dag storage is dirty when its source file metadata last cleaned timestamp is missing. [dirty_when_last_cleaned_missing]
- A node in dag storage is dirty when its source file metadata contains unacted feedback entries. [dirty_when_feedback_present]
- A node in dag storage synthesizes feedback messages for unacted feedback entries. [synthesize_feedback_messages]
- A node in dag storage is dirty when its source file metadata contains a dirty tag. [dirty_when_metadata_dirty]
- A node in dag storage synthesizes a change message when its source file metadata contains a dirty tag. [synthesize_change_message_when_metadata_dirty]
- A node in dag storage is dirty when a non-silent forward dependency has a last changed timestamp strictly newer than the node's last cleaned timestamp. [dirty_when_dependency_newer]
- A node in dag storage synthesizes a change message when a non-silent forward dependency has a newer change timestamp. [synthesize_change_message_when_dependency_newer]
- Marking a node clean clears recorded messages for the node. [mark_node_clean_in_storage]
- Marking a node clean updates the source file in-band metadata with the current timestamp as the last cleaned timestamp. [update_last_cleaned_on_clean]
- Marking a node clean with a change description updates the last changed timestamp and change description in source metadata. [mark_clean_with_change_description]
- Marking a node clean removes unacted feedback entries from source metadata. [clear_feedback_on_clean]
- Marking a node clean removes the dirty tag from source metadata. [clear_dirty_on_clean]
- Deleting the last cleaned timestamp from a node source file metadata header marks the node dirty without modifying its change description or last changed timestamp. [delete_last_cleaned_marks_dirty]
- Recording a feedback message against a dependency target node appends an unacted feedback entry to the target's source metadata. [append_feedback_to_target_metadata]
- Marking a node dirty updates its in-band metadata with a dirty tag. [mark_node_dirty_updates_dirty_tag]
- Marking a node dirty clears its last cleaned status in in-band metadata. [mark_node_dirty_clears_last_cleaned]
- Marking a subgraph clean materializes missing templates for all nodes in the subgraph. [mark_subgraph_clean_materializes_templates]
- Marking a subgraph clean marks all nodes in the subgraph clean in graph storage. [mark_subgraph_clean_marks_all_clean]
- Propagating dependencies exclude silent dependencies declared on a node when evaluating dirty status. [exclude_silent_dependencies_from_propagation]
- An auditor node in dag storage is dirty when any verified feedback target file is missing from the workspace root. [dirty_when_feedback_target_missing]
- An auditor node in dag storage is dirty when any verified feedback target node evaluates as dirty. [dirty_when_feedback_target_dirty]
- An auditor node in dag storage is dirty when any verified feedback target file metadata is missing. [dirty_when_feedback_target_metadata_missing]
- An auditor node in dag storage is dirty when any verified feedback target file metadata is unparseable. [dirty_when_feedback_target_metadata_unparseable]
- An auditor node in dag storage is dirty when any verified feedback target file is missing the auditor role audit timestamp. [dirty_when_audit_timestamp_missing]
- An auditor node in dag storage is dirty when a verified feedback target file has a last changed timestamp strictly newer than its audit timestamp. [dirty_when_feedback_target_newer_than_audit]
- An auditor node in dag storage is dirty when a non-silent contract dependency has a last changed timestamp strictly newer than a verified feedback target file audit timestamp. [dirty_when_contract_newer_than_audit]
- Marking an auditor node clean records the current timestamp as the auditor role audit timestamp on each verified feedback target file in-band metadata. [mark_auditor_node_clean_stamps_dependencies]
- Marking an auditor node clean preserves the last changed timestamp of each verified feedback target file in-band metadata. [preserve_target_last_changed_on_audit]
- Deleting the last cleaned timestamp from an auditor node removes the auditor role audit timestamp from each verified feedback target file in-band metadata. [delete_audit_timestamp_on_delete_last_cleaned]
- Materializing template writes configured template content or executes configured role template commands into declared source files when missing. [materialize_template_writes_missing_files]
- Materializing template preserves existing declared source files without overwriting. [materialize_template_preserves_existing_files]

### Woven Contracts

- The storage implementation records declared source file paths, forward dependencies, silent source file paths, and feedback dependencies, maintaining in-memory definitions and task prompts while failing fast on unconfigured auditor nodes and excluding silent dependencies from dirty propagation. [maintain_node_definitions, maintain_task_prompts, maintain_source_paths, maintain_forward_dependencies, maintain_feedback_dependencies, record_source_file_path, store_forward_dependencies, store_silent_source_files, store_feedback_dependencies, fail_unconfigured_auditor_feedback_dependencies, fail_unconfigured_auditor_dirty_evaluation, exclude_silent_dependencies_from_propagation, agent_storage: [maintain_workspace_targets, provide_task_prompts, provide_node_definitions], dag_storage: [access_dag_dependencies]]
- Nodes are evaluated as dirty if their source file is missing, if metadata or its last cleaned timestamp is missing or invalid, if a dirty tag is present, if feedback is present, or if an upstream non-silent dependency was changed after the node was last cleaned. [dirty_when_source_missing, record_change_message_when_source_missing, dirty_when_metadata_invalid, dirty_when_last_cleaned_missing, dirty_when_metadata_dirty, synthesize_change_message_when_metadata_dirty, dirty_when_feedback_present, synthesize_feedback_messages, dirty_when_dependency_newer, synthesize_change_message_when_dependency_newer, resolve_source_path, extract_in_band_metadata, dag_storage: [expose_node_dirty, dirty_when_source_missing, dirty_when_metadata_invalid, dirty_when_feedback_present, dirty_when_dependency_newer], file_paths: [resolve_ws_path]]
- Marking a node clean rewrites its in-band source header with updated timestamps and clears feedback and dirty tags, while recording feedback appends an entry to the blamed target header. [mark_node_clean_in_storage, update_last_cleaned_on_clean, mark_clean_with_change_description, clear_feedback_on_clean, clear_dirty_on_clean, append_feedback_to_target_metadata, resolve_source_path, dag_storage: [mark_node_clean_in_storage, mark_clean_updates_change_timestamp, mark_clean_records_change_summary, mark_clean_clears_feedback, mark_clean_clears_dirty_tags]]
- Marking a node dirty removes its clean status and records a dirty tag in in-band metadata without modifying its change description or last changed timestamp. [mark_node_dirty_updates_dirty_tag, mark_node_dirty_clears_last_cleaned, delete_last_cleaned_marks_dirty, resolve_source_path, dag_storage: [mark_node_dirty, mark_dirty_clears_clean_status]]
- Marking a subgraph clean materializes templates and marks the target node and all reachable dependencies clean in graph storage. [mark_subgraph_clean_materializes_templates, mark_subgraph_clean_marks_all_clean, resolve_source_path, dag_storage: [mark_subgraph_clean, subgraph_clean_marks_target_clean, subgraph_clean_marks_dependencies_clean]]
- Auditor nodes evaluate as dirty when any feedback target is missing, dirty, missing an audit timestamp, or superseded by target or contract modifications. [dirty_when_feedback_target_missing, dirty_when_feedback_target_dirty, dirty_when_feedback_target_metadata_missing, dirty_when_feedback_target_metadata_unparseable, dirty_when_audit_timestamp_missing, dirty_when_feedback_target_newer_than_audit, dirty_when_contract_newer_than_audit, resolve_source_path, extract_in_band_metadata, dag_storage: [expose_node_dirty]]
- Marking an auditor node clean stamps the audit timestamp across verified target headers without altering target change timestamps, while deleting clean status removes the audit tag. [mark_auditor_node_clean_stamps_dependencies, preserve_target_last_changed_on_audit, delete_audit_timestamp_on_delete_last_cleaned, resolve_source_path, dag_storage: [mark_auditor_node_clean_stamps_dependencies, mark_node_dirty]]
- Materializing template writes starter templates or executes template commands for missing source files and preserves existing files. [materialize_template_writes_missing_files, materialize_template_preserves_existing_files, dag_storage: [materialize_node_template]]

## Grounding

### Knowledge Provisions

- Manifest-backed agent and dag storage with in-band source metadata persistence. [src_storage_service]

### Inherited Deferred Requirements

- Source artifact inspection and in-band header parsing on the underlying filesystem.
  - Grounded: [src_metadata: [source_metadata_service], file_paths: [path_resolution_service]]
- Stamping clean metadata, clearing messages, and template materialization on disk.
  - Grounded: [src_metadata: [source_metadata_service], file_paths: [path_resolution_service]]

### Knowledge Requirements

- Resolving source paths and extracting in-band metadata.
  - Grounded: [src_metadata: [source_metadata_service], file_paths: [path_resolution_service]]
- Updating in-band metadata timestamps, feedback, and change descriptions.
  - Grounded: [src_metadata: [source_metadata_service]]
