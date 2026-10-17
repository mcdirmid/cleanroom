<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:25:00Z
CHANGE: Define check_impl planning specification
CODE_HASH: f0ad43d2e8b1
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# check_impl implementation component

## Intent

Operating command-line subagents in isolated role workspaces requires robust developer loop commands that pull changes from canonical workspaces, evaluate ready targets, enforce task completion, and execute file verification rules with starter template regeneration. The check_impl implementation component realizes get_work and check_files execution within the agent session lifecycle tier.

## Factored Contracts

### Contracts

- The workspace checker pulls inbound changes from the canonical main workspace during work execution, verifies whether prior dirty targets remain pending in the role workspace via the pending manager, resolves batch size and feedback throttling limits, evaluates ready and blocked items from the work manager, records the bounded batch of pending targets via the pending manager, presents exclusively the assigned ready targets without extraneous remaining or blocked queue details, throttling unacted feedback reasons exceeding maximum character limits, and formats actionable next steps. [execute_workspace_get_work]
- The workspace checker resolves the active role and target files during check files execution, regenerates a missing target file from its starter template for roles that declare source patterns and upstream dependencies before verification, executes the corresponding static linting, type-checking, or test rules, surfaces warning notifications and unacted feedback items when targets carrying unaddressed feedback pass static verification checks to alert agents that static checks do not verify runtime behavior or test assertions, formats clean diagnostic outcomes, and returns the verification exit status. [execute_workspace_check_files]

### Woven Contracts

- When executing get_work or check_files commands, the checker coordinates with work, pending, sync, submit, and role_registry. [execute_workspace_get_work, execute_workspace_check_files, check: [run_workspace_get_work, run_workspace_check_files], work: [compute_role_work_queue_targets, bound_ready_items_by_batch_size], pending: [get_pending_work_targets, is_pending_target_dirty_disk, set_pending_work_targets], sync: [pull_upstream_contracts, refresh_system_files_into_workspace], submit: [assert_verification_passed], role_registry: [resolve_role_definition]]

## Grounding

### Knowledge Provisions

- Work queue evaluation, batch presentation, and feedback throttling mechanics. [work_discovery_command_mechanics]
- Target verification, static lint execution, and starter template regeneration mechanics. [target_checking_command_mechanics]

### Inherited Deferred Requirements

- In-workspace work queue discovery and diagnostic formatting.
  - Grounded: [work_discovery_command_mechanics, work: [workspace_work_discovery_service], pending: [workspace_pending_work_tracking]]
- Target file verification, linting, and starter template regeneration.
  - Grounded: [target_checking_command_mechanics, submit: [file_submission_gating_service], role_registry: [workspace_registry_service]]

### Knowledge Requirements

- Workspace role definition resolution and pattern matching.
  - Grounded: [role_registry: [workspace_registry_service]]
- Work queue scheduling and candidate discovery.
  - Grounded: [work: [workspace_work_discovery_service]]
- Pending work buffer state management and target tracking.
  - Grounded: [pending: [workspace_pending_work_tracking]]
- Workspace file synchronization and inbound changes pulling.
  - Grounded: [sync: [workspace_pull_service]]
- Submission target resolution and verification.
  - Grounded: [submit: [file_submission_gating_service]]
