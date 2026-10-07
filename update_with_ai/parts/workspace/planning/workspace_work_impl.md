<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: 60fab809e202
-->

# workspace_work_impl implementation component

imports: agent_session, workspace_registry, control_work_scheduler, src_metadata
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

### Woven Contracts

- When checking work status, the work manager checks the pending buffer, invokes the work scheduler with dir_scope, writes ready targets to disk, and renders the text summary. [read_and_check_pending_buffer, invoke_scheduler_with_dir_scope, write_ready_targets_buffer, render_work_queue_text_summary, workspace_work: [check_pending_work_status, discover_directory_scope_work, record_ready_targets_buffer, format_work_queue_diagnostics], control_work_scheduler: [work_scheduling_service]]
- When all targets are clean, the manager deletes the pending work buffer and renders a clean summary. [delete_pending_work_buffer, render_work_queue_text_summary, workspace_work: [clear_pending_work_buffer]]

## Grounding

### Knowledge Provisions

- Pending target buffer reading, writing, and deletion mechanics. [pending_work_buffer_mechanics]
- Queue formatting and diagnostic text generation logic. [queue_diagnostic_rendering_logic]

### Inherited Deferred Requirements

- Persistence and evaluation of pending target lists on disk.
  - Grounded: [pending_work_buffer_mechanics]

### Knowledge Requirements

- Work discovery across directory scopes via the work scheduler.
  - Grounded: [control_work_scheduler: [work_schedule_provision]]
- In-band source metadata extraction.
  - Grounded: [src_metadata: [source_metadata_service]]
- File reading and writing on the filesystem.
  - Grounded: [pending_work_buffer_mechanics, queue_diagnostic_rendering_logic]
