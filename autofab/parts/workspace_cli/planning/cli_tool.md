# cli_tool interface component

## Intent

Autonomous subagents executing inside isolated Cleanroom role workspaces rely on a unified suite of bin utilities to inspect work queues, submit compliant changes, blame defects, and report diagnostics. Without a consistent and declarative CLI runner interface, command handling logic becomes fragmented across entrypoints, leading to inconsistent error reporting, missing dirty state synchronization, and uncontrolled execution across workspace boundaries. The cli_tool interface component defines structured command execution contracts and result formulations for role workspaces.

## Factored Contracts

### Typing

- A workspace tool runner operates within the agent session lifecycle tier as a singleton service.

### Contracts

- The workspace tool runner dispatches CLI arguments across role subcommands and executes the selected action. [dispatch_role_subcommand]
- The workspace tool runner coordinates get_work execution by checking pending targets, bounding presented ready items by batch size, resolving feedback character limits, evaluating the queue, presenting exclusively the bounded assigned batch without extraneous remaining or blocked queue details, throttling feedback reasons exceeding character limits, and formatting diagnostic next steps with target files and companion specification contracts. [execute_get_work_command]
- The workspace tool runner coordinates check_files execution by running role-specific static linters and type checkers for target files, regenerating missing target files from starter templates for roles with declared source patterns and upstream dependencies. [execute_check_files_command]
- The workspace tool runner coordinates submit execution by evaluating verification checks on the target, committing staged blame feedback to culprits when staged blame exists for a failing target, disallowing manual submission without preceding blame in auditor roles, rejecting failing targets without staged blame unless bypassed, updating metadata, appending to the cleanroom log, and clearing pending targets upon success. [execute_submit_command]
- The workspace tool runner coordinates blame and feedback execution by supporting structured blame options (--slug, --viol, --facet, --lines, --witness), validating critique constraints, staging critique feedback for subsequent commit upon submit, and notifying the caller to stage additional blame or commit staged blame. [execute_blame_command]
- The workspace tool runner coordinates reject execution by verifying the target file has not been modified since receiving feedback, removing the feedback header block from the target file, recording the contest explanation into the workspace blame buffer and log, and clearing pending targets upon success. [execute_reject_command]
- The workspace tool runner coordinates fail execution by applying dirty tags, recording failure feedback, and clearing pending targets. [execute_fail_command]
- The workspace tool runner coordinates statement test coverage evaluation and outputs diagnostics. [execute_coverage_command]
- The workspace tool runner coordinates restoring modified files or the entire workspace tree from git snapshot points, and creating git commit checkpoints of active workspace state. [execute_revert_and_checkpoint_command]
- The workspace tool runner coordinates workspace commissioning for specified roles or across all declared roles within a directory scope, dynamically discovering or requiring the directory scope without hardcoded defaults, supporting resetting stale work buffers and stamping model execution profiles. [execute_commission_command]
- The workspace tool runner coordinates system file, binary utility, and guide refresh across active workspaces. [execute_refresh_sys_command]

### Woven Contracts

- When get_work executes, the runner delegates work queue discovery to the work manager, records pending targets, and formats console diagnostics with companion contract paths. [execute_get_work_command]

## Grounding

### Knowledge Provisions

- Role workspace command execution and CLI dispatch services. [workspace_tool_runner_service]

### Knowledge Requirements

- Agent session lifecycle phase and context management.
  - Grounded: [session: [agent_session_tier_provision]]
- Cleanroom log file naming conventions.
  - Grounded: [autofab_files_ext: [autofab_files_schema]]
- Dispatch and execution of role workspace commands.
  - Deferred: Provided by workspace tool runner realization.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-07T10:20:00Z
CHANGE: Add reject runner and update submit and blame staging and auditor blame requirements
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
