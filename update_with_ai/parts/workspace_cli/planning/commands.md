<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:50:00Z
CHANGE: Define commands planning specification
CODE_HASH: f68f94348892
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# commands interface component

## Intent

Autonomous subagents executing inside isolated role workspaces require standard handlers to execute domain operations without entangling argument parsing with business workflows. The commands interface component defines structured command execution methods and exit codes for all workspace operations including work discovery, file verification, change submission, defect blame attribution, statement coverage analysis, workspace commissioning, and system synchronization.

## Factored Contracts

### Typing

- An agent session's workspace command handler provides domain command execution for cleanroom role workspaces.

### Contracts

- The command handler evaluates dirty work in the local role workspace, presenting bounded batches of ready targets without extraneous remaining or blocked queue details, throttling unacted feedback reasons exceeding maximum character limits when configured, and returning an integer exit code. [execute_get_work_command]
- The command handler executes role-specific verification checks, linters, and type checking for specified or pending target files, regenerating missing target files from starter templates before verification for roles with source patterns and upstream dependencies, surfacing unacted feedback warnings when targets carrying unaddressed feedback pass static verification, and returning the verification exit code. [execute_check_files_command]
- The command handler submits target files to the canonical main repository, rejecting failing targets unless bypassed, enforcing producer change summaries, attesting auditor stamps, appending submission records to the cleanroom log in both the canonical repository and local workspace, and clearing the target from pending work buffers on success. [execute_submit_command]
- The command handler attributes defect blame or failure diagnostics to culprit targets, propagating single-paragraph critique feedback, appending blame records to the cleanroom log in both the canonical repository and local workspace, and clearing the target from pending work buffers on success. [execute_blame_command]
- The command handler records failure diagnostics for culprit targets and clears the target from pending work buffers on success. [execute_fail_command]
- The command handler evaluates statement test coverage across implementation and test pairs against target thresholds, formatting span diagnostics and returning an integer exit code. [execute_coverage_command]
- The command handler commissions isolated role workspaces for specified roles or across all declared roles within a directory scope, dynamically discovering or requiring the directory scope without hardcoded defaults, supporting resetting stale work buffers and stamping model execution profiles. [execute_commission_command]
- The command handler refreshes system configuration files, bin utilities, and companion guides across active role workspaces. [execute_refresh_sys_command]

### Woven Contracts

- When evaluating dirty work, the command handler pulls changes, evaluates ready items, tracks pending targets, and prints structured reports. [execute_get_work_command]
- When submitting changes or attributing blame, the command handler validates target constraints, records actions in cleanroom logs, and clears pending work buffers upon success. [execute_submit_command, execute_blame_command, execute_fail_command]

## Grounding

### Knowledge Provisions

- Role workspace domain command execution workflows. [workspace_commands_service]

### Knowledge Requirements

- Agent session lifecycle phase and context management.
  - Grounded: [session: [agent_session_tier_provision]]
- Cleanroom log file naming conventions.
  - Grounded: [cleanroom_files_ext: [cleanroom_files_schema]]
- Domain execution of workspace commands across cleanroom subsystems.
  - Deferred: Provided by workspace command handler realization.
