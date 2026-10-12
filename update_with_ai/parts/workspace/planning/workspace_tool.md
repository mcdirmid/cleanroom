<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T16:00:00Z
CHANGE: update execute_submit_command contract for verification gating and bypass
CODE_HASH: 7d5eefb7b555
SPEC_QA_AUDIT: 2026-10-12T18:21:03Z
-->

# workspace_tool interface component

## Intent

Autonomous subagents executing inside isolated Cleanroom role workspaces rely on a unified suite of bin utilities to inspect work queues, submit compliant changes, blame defects, and report diagnostics. Without a consistent and declarative CLI runner interface, command handling logic becomes fragmented across entrypoints, leading to inconsistent error reporting, missing dirty state synchronization, and uncontrolled execution across workspace boundaries. The workspace_tool interface component defines structured command execution contracts and result formulations for role workspaces.

## Factored Contracts

### Typing

- A workspace tool runner operates within the agent session lifecycle tier as a singleton service.

### Contracts

- The workspace tool runner dispatches CLI arguments across role subcommands and executes the selected action. [dispatch_role_subcommand]
- The workspace tool runner coordinates get_work execution by checking pending targets, evaluating the queue, and formatting diagnostic next steps with target files and companion specification contracts. [execute_get_work_command]
- The workspace tool runner coordinates check_files execution by running role-specific static linters and type checkers for target files, regenerating missing target files from starter templates for roles with declared source patterns and upstream dependencies. [execute_check_files_command]
- The workspace tool runner coordinates submit execution by evaluating verification checks on the target and rejecting failing targets unless bypassed, updating metadata, appending to the cleanroom log, and clearing pending targets upon success. [execute_submit_command]
- The workspace tool runner coordinates blame and feedback execution by validating critique constraints, injecting feedback, appending to the cleanroom log, and clearing pending targets. [execute_blame_command]
- The workspace tool runner coordinates fail execution by applying dirty tags, recording failure feedback, and clearing pending targets. [execute_fail_command]
- The workspace tool runner coordinates statement test coverage evaluation and outputs diagnostics. [execute_coverage_command]
- The workspace tool runner coordinates workspace commissioning and returns directory results. [execute_commission_command]
- The workspace tool runner coordinates system file, binary utility, and guide refresh across active workspaces. [execute_refresh_sys_command]

### Woven Contracts

- When get_work executes, the runner delegates work queue discovery to the work manager, records pending targets, and formats console diagnostics with companion contract paths. [execute_get_work_command]

## Grounding

### Knowledge Provisions

- Role workspace command execution and CLI dispatch services. [workspace_tool_runner_service]

### Knowledge Requirements

- Agent session lifecycle phase and context management.
  - Grounded: [agent_session: [agent_session_tier_provision]]
- Cleanroom log file naming conventions.
  - Grounded: [cleanroom_files_ext: [cleanroom_files_schema]]
