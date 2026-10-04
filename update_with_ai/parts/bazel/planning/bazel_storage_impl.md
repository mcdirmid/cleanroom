# bazel_storage_impl implementation component

imports: bazel_target, file_paths, src_metadata_ext
implements: agent_storage, dag_storage

## Intent

Coordinating multi-node builds requires fast in-memory access to target metadata alongside durable on-disk persistence of inter-node communication records. Storing inter-node communication records in sidecar package files causes state desynchronization, ghost records, and merge conflicts across branches. The bazel_storage_impl implementation component resolves declared source files against the workspace root, extracts and updates in-band comment headers using src_metadata_ext, evaluates dirty status dynamically from forward dependency timestamps and unacted feedback, and filters silent dependencies from dirty propagation.

By storing clean status, change summaries, and feedback directly within source files, the implementation provides transparent, self-describing provenance that synchronizes atomically with version control.

## Factored Contracts

### Contracts

- The agent storage maintains node definitions mapped to nodes in dag storage. [maintain_node_definitions]
- The agent storage maintains task prompts mapped to nodes in dag storage. [maintain_task_prompts]
- The agent storage maintains declared source paths mapped to nodes in dag storage. [maintain_source_paths]
- The agent storage maintains forward dependencies mapped to nodes in dag storage. [maintain_forward_dependencies]
- The agent storage resolves declared source paths against the workspace root. [resolve_source_path]
- The agent storage extracts in-band metadata from declared source files. [extract_in_band_metadata]
- A node in dag storage is dirty when its declared source file is missing from the workspace root. [dirty_when_source_missing]
- A node in dag storage records a change message to implement the source file when its source file is missing. [record_change_message_when_source_missing]
- A node in dag storage is dirty when its source file metadata is missing or unparseable. [dirty_when_metadata_invalid]
- A node in dag storage is dirty when its source file metadata last cleaned timestamp is missing. [dirty_when_last_cleaned_missing]
- A node in dag storage is dirty when its source file metadata contains unacted feedback entries. [dirty_when_feedback_present]
- A node in dag storage synthesizes feedback messages for unacted feedback entries. [synthesize_feedback_messages]
- A node in dag storage is dirty when a non-silent forward dependency has a last changed timestamp strictly newer than the node's last cleaned timestamp. [dirty_when_dependency_newer]
- A node in dag storage synthesizes a change message when a non-silent forward dependency has a newer change timestamp. [synthesize_change_message_when_dependency_newer]
- Marking a node clean updates the source file in-band metadata with the current timestamp as the last cleaned timestamp. [update_last_cleaned_on_clean]
- Marking a node clean with workspace file modifications updates the last changed timestamp and change description in source metadata. [update_last_changed_on_clean_with_mods]
- Marking a node clean removes unacted feedback entries from source metadata. [clear_feedback_on_clean]
- Deleting the last cleaned timestamp from a node source file metadata header marks the node dirty without modifying its change description or last changed timestamp. [delete_last_cleaned_marks_dirty]
- Recording a feedback message against a dependency target node appends an unacted feedback entry to the target's source metadata. [append_feedback_to_target_metadata]
- Propagating dependencies exclude silent dependencies declared on a node when evaluating dirty status. [exclude_silent_dependencies_from_propagation]

## Woven Contracts

- The storage implementation maintains in-memory node definitions, task prompts, and declared source paths, excluding silent dependencies from dirty propagation. [maintain_node_definitions, maintain_task_prompts, maintain_source_paths, maintain_forward_dependencies, exclude_silent_dependencies_from_propagation, agent_storage: [maintain_workspace_targets, provide_task_prompts, provide_node_definitions], dag_storage: [access_dag_dependencies]]
- Nodes are evaluated as dirty if their source file is missing, if metadata or its last cleaned timestamp is missing or invalid, if feedback is present, or if an upstream non-silent dependency was changed after the node was last cleaned. [dirty_when_source_missing, record_change_message_when_source_missing, dirty_when_metadata_invalid, dirty_when_last_cleaned_missing, dirty_when_feedback_present, synthesize_feedback_messages, dirty_when_dependency_newer, synthesize_change_message_when_dependency_newer, resolve_source_path, extract_in_band_metadata, dag_storage: [expose_node_dirty, dirty_when_source_missing, dirty_when_metadata_invalid, dirty_when_feedback_present, dirty_when_dependency_newer], file_paths: [resolve_ws_path], src_metadata_ext: [parse_last_cleaned_timestamp, parse_last_changed_timestamp, parse_change_description, parse_unacted_feedback_list]]
- Marking a node clean rewrites its in-band source header with updated timestamps and clears feedback, while recording feedback appends an entry to the blamed target header. [update_last_cleaned_on_clean, update_last_changed_on_clean_with_mods, clear_feedback_on_clean, append_feedback_to_target_metadata, resolve_source_path, src_metadata_ext: [rewrite_last_cleaned_timestamp, rewrite_last_changed_timestamp, rewrite_change_description, rewrite_append_feedback, rewrite_remove_feedback, rewrite_preserve_body]]
- Deleting the last cleaned timestamp from a node source file metadata header marks the node dirty without modifying its change description or last changed timestamp. [delete_last_cleaned_marks_dirty, resolve_source_path, dag_storage: [mark_node_dirty], src_metadata_ext: [rewrite_clear_last_cleaned, rewrite_preserve_body]]
