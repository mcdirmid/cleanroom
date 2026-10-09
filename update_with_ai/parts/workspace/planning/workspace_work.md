<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-08T15:45:00Z
CHANGE: update is_pending_target_dirty_disk contract for regenerable roles template materialization
CODE_HASH: a3ad69a4c8ea
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# workspace_work interface component

imports: agent_session, workspace_registry, control_work_scheduler, src_metadata, dag_storage

## Intent

Autonomous agents operating without subgraphs or full DAG models require accurate, directory-scoped work discovery to determine which targets need cleaning, which are blocked by upstream prerequisites, and when turns can terminate cleanly. Guessing work status or scanning files ad-hoc wastes context tokens, causes out-of-order execution, and results in premature turn termination. The workspace_work interface component establishes contracts for querying ready tasks using dynamic role precedence, inspecting pending work buffers, computing actionable next steps, and tracking pending targets across turns.

## Factored Contracts

### Typing

- A work queue item record encapsulates a target file, a role name, a sequence of dirtiness reasons, a sequence of dependency files, a sequence of companion contract files, an optional blocked reason, and an is ready flag.
- A work queue summary record encapsulates a sequence of ready items, a sequence of blocked items, and an is clean flag.
- A workspace work manager operates within the agent session lifecycle tier.

### Contracts

- The workspace work manager inspects .cleanroom_pending_work.json to check whether pending targets remain dirty. [check_pending_work_status]
- The workspace work manager clears .cleanroom_pending_work.json when no pending targets remain dirty. [clear_pending_work_buffer]
- The workspace work manager invokes directory-scoped work discovery to compute ready and blocked units. [discover_directory_scope_work]
- The workspace work manager resolves companion upstream specification contract files and interface definitions for target units dynamically from workspace_registry. [resolve_unit_contract_files]
- The workspace work manager filters cross-unit dependencies based on star_role_deps and silent_cross_role_deps from workspace_registry. [filter_role_dependencies]
- The workspace work manager enforces fail-loud role resolution without synthetic fallbacks. [enforce_strict_role_resolution]
- The workspace work manager materializes starter templates via graph storage for missing ready target files. [materialize_ready_target_templates]
- The workspace work manager records ready targets into .cleanroom_pending_work.json upon discovery. [record_ready_targets_buffer]
- The workspace work manager formats actionable diagnostic next steps for ready and blocked queue items. [format_work_queue_diagnostics]
- The workspace work manager records assigned target paths into the pending work buffer file. [set_pending_work_targets]
- The workspace work manager removes a resolved target path from the pending work buffer file. [remove_pending_target_path]
- The workspace work manager evaluates whether a pending target remains dirty on disk, materializing starter templates via graph storage for missing targets of roles with source patterns and upstream dependencies. [is_pending_target_dirty_disk]
- The workspace work manager computes role work queues by discovering dirty units and sorting ready units topologically. [compute_role_work_queue_targets]

### Woven Contracts

- When discovering work in a role workspace, the manager checks pending work status, discovers directory scope work if unblocked, resolves companion contracts, filters cross-unit dependencies according to star and silent role rules, materializes starter templates for missing ready files, records ready targets, and formats diagnostic outputs. [check_pending_work_status, discover_directory_scope_work, resolve_unit_contract_files, filter_role_dependencies, enforce_strict_role_resolution, materialize_ready_target_templates, record_ready_targets_buffer, format_work_queue_diagnostics, workspace_registry: [resolve_role_definition, list_roles], control_work_scheduler: [discover_directory_candidates, filter_ready_dependencies], src_metadata: [extract_metadata_disk], dag_storage: [materialize_node_template]]
- When all targets in scope evaluate clean, the manager clears the pending work buffer and indicates clean status. [clear_pending_work_buffer, discover_directory_scope_work]
- When a target is resolved, the work manager removes the target from the pending buffer and checks whether any pending work remains dirty. [remove_pending_target_path, is_pending_target_dirty_disk, src_metadata: [extract_metadata_disk]]

## Grounding

### Knowledge Provisions

- Directory-scoped work queue discovery and diagnostic presentation services. [workspace_work_discovery_service]
- Pending work buffer state management and target tracking capabilities. [workspace_pending_work_tracking]
- Role work queue computation and topological unit sorting capabilities. [role_work_queue_computation_service]

### Knowledge Requirements

- Topological scheduling and dirtiness evaluation across directory scopes.
  - Grounded: [control_work_scheduler: [work_schedule_provision]]
- Extraction and inspection of in-band source metadata headers.
  - Grounded: [src_metadata: [source_metadata_service]]
- Materialization of starter templates for missing target files.
  - Grounded: [dag_storage: [materialize_node_template]]
- Persistence and evaluation of pending target lists on disk.
  - Deferred: Provided by workspace work manager implementation.
