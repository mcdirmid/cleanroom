# commands interface component

## Intent

Autonomous subagents executing inside isolated role workspaces require standard handlers to execute domain operations without entangling argument parsing with business workflows. The commands interface component defines structured command execution methods and exit codes for all workspace operations including work discovery, file verification, change submission, defect blame attribution, statement coverage analysis, workspace commissioning, and system synchronization.

## Factored Contracts

### Typing

- An agent session's workspace command handler provides domain command execution for cleanroom role workspaces.

### Contracts

- The command handler evaluates dirty work in the local role workspace, presenting bounded batches of ready targets without extraneous remaining or blocked queue details, throttling unacted feedback reasons exceeding maximum character limits when configured, and returning an integer exit code. [execute_get_work_command]
- The command handler executes role-specific verification checks, linters, and type checking for specified or pending target files, regenerating missing target files from starter templates before verification for roles with source patterns and upstream dependencies, surfacing unacted feedback warnings when targets carrying unaddressed feedback pass static verification, and returning the verification exit code. [execute_check_files_command]
- The command handler submits target files to the canonical main repository, enforcing that modified target files have been checked via check_files since their latest modifications unless bypassed, committing staged blame feedback to culprit metadata and dirtying culprits when staged blame exists for a failing target, disallowing manual submission without preceding blame in auditor roles, rejecting failing targets without staged blame unless bypassed, enforcing producer change summaries, attesting auditor stamps, appending submission records to the Autofab log in both the canonical repository and local workspace, and clearing the target from pending work buffers on success. [execute_submit_command]
- The command handler attributes defect blame or failure diagnostics to culprit targets, enforcing that any modified workspace target files have been checked via check_files since their latest modifications, validating the structured blame tuple (specification slug grounding in low-level specifications, violation code taxonomy, noun phrase facet constraints, and zero-entropy symbol embargo) when the structured blame experiment is active, staging single-paragraph critique feedback for subsequent submission commit, recording blamed culprit targets into the workspace blame buffer, and notifying the caller to stage additional blame or commit staged blame via submit. [execute_blame_command]
- The command handler rejects active feedback delivered to an unmodified target file, enforcing that the target file has not been modified since receiving feedback, immediately removing the feedback comment block from the target file header, recording the contest explanation into the workspace blame buffer and event log, and clearing the target from pending work buffers on success. [execute_reject_command]
- The command handler records failure diagnostics for culprit targets, enforcing that modified target files have been checked via check_files since their latest modifications, and clearing the target from pending work buffers on success. [execute_fail_command]
- The command handler evaluates statement test coverage across implementation and test pairs against target thresholds, formatting span diagnostics and returning an integer exit code. [execute_coverage_command]
- The command handler commissions isolated role workspaces for specified roles or across all declared roles within a directory scope, dynamically discovering or requiring the directory scope without hardcoded defaults, supporting resetting stale work buffers and stamping model execution profiles. [execute_commission_command]
- The command handler refreshes system configuration files, bin utilities, and companion guides across active role workspaces. [execute_refresh_sys_command]

### Woven Contracts

- When evaluating dirty work, the command handler pulls changes, evaluates ready items, tracks pending targets, and prints structured reports. [execute_get_work_command]
- When submitting changes, rejecting feedback, or attributing blame, the command handler validates target constraints, records actions in Autofab logs, and clears pending work buffers upon success. [execute_submit_command, execute_blame_command, execute_reject_command, execute_fail_command]

## Grounding

### Knowledge Provisions

- Role workspace domain command execution workflows. [workspace_commands_service]

### Knowledge Requirements

- Agent session lifecycle phase and context management.
  - Grounded: [session: [agent_session_tier_provision]]
- Autofab log file naming conventions.
  - Grounded: [autofab_files_ext: [autofab_files_schema]]
- Domain execution of workspace commands across Autofab subsystems.
  - Deferred: Provided by workspace command handler realization.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-07T10:20:00Z
CHANGE: Specify reject command and stage-and-commit blame submission workflow with auditor blame requirement
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
