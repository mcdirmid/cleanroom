<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: 3a53ef0e2ba7
-->

# workspace_work interface component

imports: agent_session, workspace_registry, control_work_scheduler, src_metadata

## Intent

Autonomous agents operating without subgraphs or full DAG models require accurate, directory-scoped work discovery to determine which targets need cleaning, which are blocked by upstream prerequisites, and when turns can terminate cleanly. Guessing work status or scanning files ad-hoc wastes context tokens, causes out-of-order execution, and results in premature turn termination. The workspace_work interface component establishes contracts for querying ready tasks using dynamic role precedence, inspecting pending work buffers, computing actionable next steps, and tracking pending targets across turns.

## Factored Contracts

### Typing

- A work queue item record encapsulates a target file, a role name, a sequence of dirtiness reasons, a sequence of dependency files, an optional blocked reason, and an is ready flag.
- A work queue summary record encapsulates a sequence of ready items, a sequence of blocked items, and an is clean flag.
- A workspace work manager operates within the agent session lifecycle tier.

### Contracts

- The workspace work manager inspects .cleanroom_pending_work.json to check whether pending targets remain dirty. [check_pending_work_status]
- The workspace work manager clears .cleanroom_pending_work.json when no pending targets remain dirty. [clear_pending_work_buffer]
- The workspace work manager invokes directory-scoped work discovery to compute ready and blocked units. [discover_directory_scope_work]
- The workspace work manager records ready targets into .cleanroom_pending_work.json upon discovery. [record_ready_targets_buffer]
- The workspace work manager formats actionable diagnostic next steps for ready and blocked queue items. [format_work_queue_diagnostics]

### Woven Contracts

- When discovering work in a role workspace, the manager checks pending work status, discovers directory scope work if unblocked, records ready targets, and formats diagnostic outputs. [check_pending_work_status, discover_directory_scope_work, record_ready_targets_buffer, format_work_queue_diagnostics, control_work_scheduler: [discover_directory_candidates, filter_ready_dependencies], src_metadata: [extract_metadata_disk]]
- When all targets in scope evaluate clean, the manager clears the pending work buffer and indicates clean status. [clear_pending_work_buffer, discover_directory_scope_work]

## Grounding

### Knowledge Provisions

- Directory-scoped work queue discovery and diagnostic presentation services. [workspace_work_discovery_service]
- Pending work buffer state management and target tracking capabilities. [workspace_pending_work_tracking]

### Knowledge Requirements

- Topological scheduling and dirtiness evaluation across directory scopes.
  - Grounded: [control_work_scheduler: [work_schedule_provision]]
- Extraction and inspection of in-band source metadata headers.
  - Grounded: [src_metadata: [source_metadata_service]]
- Persistence and evaluation of pending target lists on disk.
  - Deferred: Provided by workspace work manager implementation.
