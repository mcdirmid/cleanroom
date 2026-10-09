<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-09T04:30:00Z
CHANGE: factor auditor unit dirtiness across all feedback targets and strict pending target removal
CODE_HASH: def76acd13d2
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# workspace_work_impl implementation component

imports: agent_session, workspace_registry, control_work_scheduler, src_metadata, dag_storage
implements: workspace_work

## Intent

Guiding autonomous agents through multi-step pipeline tasks requires distinguishing ready targets from targets blocked on upstream artifacts while enforcing completion of pending work before starting new tasks. Without strict queue tracking, agents jump between disconnected files or exit before completing verification. The workspace_work_impl implementation component invokes directory-scoped work scheduling, filters candidates by active role, evaluates pending target dirtiness against local and main workspaces, persists pending target state in .cleanroom_pending_work.json, and generates structured task outputs with actionable guidance.

## Factored Contracts

### Contracts

- The workspace work manager reads target paths from .cleanroom_pending_work.json and evaluates metadata dirtiness. [read_and_check_pending_buffer]
- The workspace work manager deletes .cleanroom_pending_work.json from disk when pending targets are resolved. [delete_pending_work_buffer]
- The workspace work manager calls schedule_work with dir_scope to obtain ready and blocked tasks. [invoke_scheduler_with_dir_scope]
- The workspace work manager writes ready target file paths to .cleanroom_pending_work.json as JSON. [write_ready_targets_buffer]
- The workspace work manager generates formatted text summaries detailing ready items, blocked items, and next actions. [render_work_queue_text_summary]
- The workspace work manager writes designated target paths into the pending work buffer file. [write_assigned_pending_targets]
- The workspace work manager filters out a submitted or blamed target path matching pending target paths or unit stems strictly without clearing unmatched targets. [filter_out_resolved_pending_target]
- The workspace work manager evaluates auditor unit dirtiness by checking in-band metadata across all configured feedback role targets against required audit timestamps and contract modifications. [evaluate_auditor_unit_dirtiness]
- The workspace work manager discovers companion specification contracts and interface files for target units on disk using role definitions from workspace_registry. [discover_unit_contract_files]
- The workspace work manager filters cross-unit dependencies using silent_cross_role_deps and expands star_role_deps from workspace_registry. [filter_and_expand_dependencies]
- The workspace work manager raises ValueError or KeyError on unrecognized roles or file paths. [fail_loud_on_unrecognized_roles]
- The workspace work manager checks local and main repository metadata to test if a pending target is dirty, materializing starter templates via graph storage for missing targets of roles with source patterns and upstream dependencies. [test_pending_target_dirty_state]
- The workspace work manager discovers part units and dependencies from build definitions, High-Level Specifications, or filesystem component stems. [discover_part_units_and_dependencies]
- The workspace work manager inspects parts in scope to compute ready and blocked role units with topological ordering. [compute_and_sort_role_work_queue]
- The workspace work manager materializes starter templates via graph storage for missing ready target files of roles with source patterns and upstream dependencies. [materialize_ready_target_templates]

### Woven Contracts

- When checking work status, the work manager checks the pending buffer, invokes the work scheduler with dir_scope, resolves companion contracts, filters cross-unit dependencies, writes ready targets to disk, and renders the text summary. [read_and_check_pending_buffer, invoke_scheduler_with_dir_scope, discover_unit_contract_files, filter_and_expand_dependencies, fail_loud_on_unrecognized_roles, write_ready_targets_buffer, render_work_queue_text_summary, workspace_work: [check_pending_work_status, discover_directory_scope_work, resolve_unit_contract_files, filter_role_dependencies, enforce_strict_role_resolution, record_ready_targets_buffer, format_work_queue_diagnostics], workspace_registry: [resolve_role_definition, list_roles], control_work_scheduler: [work_scheduling_service]]
- When computing role work queues, the work manager discovers part units and dependencies across parts in scope, evaluates auditor units across all feedback targets, materializes starter templates via graph storage for missing ready files, and sorts ready and blocked units topologically. [discover_part_units_and_dependencies, evaluate_auditor_unit_dirtiness, compute_and_sort_role_work_queue, materialize_ready_target_templates, workspace_work: [compute_role_work_queue_targets, materialize_ready_target_templates], dag_storage: [materialize_node_template]]
- When all targets are clean, the manager deletes the pending work buffer and renders a clean summary. [delete_pending_work_buffer, render_work_queue_text_summary, workspace_work: [clear_pending_work_buffer]]
- When managing target assignments, the work manager writes assigned targets to disk, removes submitted targets, and checks dirtiness against repository metadata. [write_assigned_pending_targets, filter_out_resolved_pending_target, test_pending_target_dirty_state, workspace_work: [set_pending_work_targets, remove_pending_target_path, is_pending_target_dirty_disk], src_metadata: [extract_metadata_disk]]

## Grounding

### Knowledge Provisions

- Pending target buffer reading, writing, and deletion mechanics. [pending_work_buffer_mechanics]
- Queue formatting and diagnostic text generation logic. [queue_diagnostic_rendering_logic]
- Role work queue computation and topological dependency sorting algorithms. [role_work_queue_algorithm]
- Part unit and dependency discovery mechanics across build definitions, specifications, and directory stems. [part_unit_discovery_mechanics]
- Auditor unit dirtiness evaluation across all feedback targets. [auditor_dirtiness_evaluation_mechanics]

### Inherited Deferred Requirements

- Persistence and evaluation of pending target lists on disk.
  - Grounded: [pending_work_buffer_mechanics]

### Knowledge Requirements

- Work discovery across directory scopes via the work scheduler.
  - Grounded: [control_work_scheduler: [work_schedule_provision]]
- In-band source metadata extraction.
  - Grounded: [src_metadata: [source_metadata_service]]
- Materialization of starter templates for missing target files.
  - Grounded: [dag_storage: [dag_storage_service]]
- File reading and writing on the filesystem.
  - Grounded: [pending_work_buffer_mechanics, queue_diagnostic_rendering_logic]
