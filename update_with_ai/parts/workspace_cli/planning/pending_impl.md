<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:40:00Z
CHANGE: Define pending_impl planning specification
CODE_HASH: 20963c47961f
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# pending_impl implementation component

## Intent

Operating command-line subagents in isolated workspaces requires durable file-based tracking of in-progress tasks to enforce task completion and prevent agents from acquiring new work while incomplete targets remain dirty. The pending_impl implementation component manages JSON-serialized pending target state in `.cleanroom_pending_work.json`, evaluates whether assigned targets remain dirty across local and canonical workspaces, and materializes starter templates via graph storage for missing targets.

## Factored Contracts

### Contracts

- The workspace pending manager reads target file paths from the pending work buffer file and returns an empty sequence when missing. [read_pending_buffer_file]
- The workspace pending manager writes designated target paths into the pending work buffer file as JSON. [write_assigned_pending_targets]
- The workspace pending manager filters out a submitted or blamed target path matching pending target paths or unit stems strictly without clearing unmatched targets. [filter_out_resolved_pending_target]
- The workspace pending manager deletes the pending work buffer file from disk when pending targets are cleared. [delete_pending_work_buffer]
- The workspace pending manager checks local and main repository metadata to test if a pending target is dirty, evaluating star role dependency modification timestamps and implicit feedback dependencies. [test_pending_target_dirty_state]
- The workspace pending manager materializes starter templates via graph storage for missing targets of roles with declared source patterns and upstream dependencies. [materialize_pending_starter_template]

### Woven Contracts

- When managing target assignments, the pending manager writes assigned targets to disk, removes submitted targets, and checks dirtiness against repository metadata. [write_assigned_pending_targets, filter_out_resolved_pending_target, test_pending_target_dirty_state, materialize_pending_starter_template, pending: [set_pending_work_targets, remove_pending_target_path, is_pending_target_dirty_disk, track_implicit_role_dirtiness, materialize_pending_target_template], src_metadata: [extract_metadata_disk], dag_storage: [materialize_node_template], role_registry: [resolve_role_definition]]
- When reading or clearing pending state, the pending manager reads the pending buffer or deletes the buffer file. [read_pending_buffer_file, delete_pending_work_buffer, pending: [get_pending_work_targets, clear_pending_work_buffer]]

## Grounding

### Knowledge Provisions

- Pending target buffer reading, writing, and deletion mechanics. [pending_work_buffer_mechanics]
- Pending target dirty checking against source metadata and role definitions. [pending_dirtiness_evaluation_mechanics]
- Starter template materialization mechanics for missing pending files. [pending_template_materialization_mechanics]

### Inherited Deferred Requirements

- Persistence and evaluation of pending target lists on disk.
  - Grounded: [pending_work_buffer_mechanics, cleanroom_files_ext: [cleanroom_files_schema]]

### Knowledge Requirements

- In-band source metadata extraction.
  - Grounded: [src_metadata: [source_metadata_service]]
- Materialization of starter templates for missing target files.
  - Grounded: [dag_storage: [dag_storage_service]]
- Workspace state and pending work file naming conventions.
  - Grounded: [cleanroom_files_ext: [cleanroom_files_schema]]
- Role definition resolution and pattern matching.
  - Grounded: [role_registry: [workspace_registry_service]]
- File reading and writing on the filesystem.
  - Grounded: [pending_work_buffer_mechanics]
