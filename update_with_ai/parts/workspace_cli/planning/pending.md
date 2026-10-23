# pending interface component

## Intent

Operating command-line subagents inside isolated role workspaces requires durable file-based tracking of in-progress tasks to enforce task completion and prevent agents from acquiring new work while incomplete targets remain dirty. The pending interface component establishes contracts for inspecting pending targets, updating the pending buffer file, removing submitted or blamed targets, and verifying whether assigned targets remain dirty across local and canonical workspaces.

## Factored Contracts

### Typing

- A workspace pending manager operates within the agent session lifecycle tier.

### Contracts

- The workspace pending manager reads target file paths from the pending work buffer file designated by cleanroom_files_ext, returning an empty sequence when missing. [get_pending_work_targets]
- The workspace pending manager records assigned target paths into the pending work buffer file. [set_pending_work_targets]
- The workspace pending manager removes matching submitted or blamed target paths and unit stems from the pending work buffer file. [remove_pending_target_path]
- The workspace pending manager deletes the pending work buffer file when cleared. [clear_pending_work_buffer]
- The workspace pending manager evaluates whether a pending target remains dirty on disk across local workspace and main repository, resolving canonical lifecycle metadata from the main repository when available. [is_pending_target_dirty_disk]
- The workspace pending manager evaluates feedback role dependencies and star role dependencies as implicit dependencies when checking pending target dirtiness. [track_implicit_role_dirtiness]
- The workspace pending manager materializes starter templates via graph storage for missing targets of roles with declared source patterns and upstream dependencies. [materialize_pending_target_template]

### Woven Contracts

- When managing active tasks in a role workspace, the pending manager records assigned targets, tracks pending state across rounds, removes completed targets upon submission or blame, and verifies whether pending targets remain dirty before allowing new work discovery. [set_pending_work_targets, get_pending_work_targets, remove_pending_target_path, is_pending_target_dirty_disk, track_implicit_role_dirtiness, materialize_pending_target_template]
- When all assigned targets evaluate clean, the pending manager clears the pending work buffer file. [clear_pending_work_buffer]

## Grounding

### Knowledge Provisions

- Pending work buffer state management and target tracking capabilities. [workspace_pending_work_tracking]
- Pending target dirtiness evaluation and starter template materialization services. [workspace_pending_dirtiness_service]

### Knowledge Requirements

- Layout conventions and state marker constants for Cleanroom workspace files.
  - Grounded: [cleanroom_files_ext: [cleanroom_files_schema]]
- Persistence and evaluation of pending target lists on disk.
  - Deferred: Provided by workspace pending manager implementation.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:40:00Z
CHANGE: Define pending planning specification
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
