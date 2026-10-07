<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T23:30:00Z
CHANGE: new file
CODE_HASH: 1d2e3f4a5b6c
-->

# workspace_tool_impl implementation component

imports: agent_session, workspace_registry, workspace_provision, workspace_sync, workspace_work, control_submit, control_attribution, tool_coverage
implements: workspace_tool

## Intent

Command-line subagents in Cleanroom workspaces require a robust entrypoint that parses subcommands, synchronizes files from canonical main workspaces, validates inputs, and triggers appropriate domain coordinators. The workspace_tool_impl implementation component consolidates argument parsing, console output rendering, and execution workflows into a singleton runner operating within the agent session lifecycle tier.

## Factored Contracts

### Typing

- The workspace tool runner realization implements WorkspaceToolRunner and operates in agent_session.

### Contracts

- The realization constructs argument parsers for commission, decommission, refresh-sys, get_work, check_files, submit, blame, fail, and coverage. [construct_cli_parser]
- In get_work, the runner pulls inbound changes from canonical main, rejects execution if pending targets remain dirty, queries the work manager, records pending targets, and formats console reports. [realize_get_work]
- In check_files, the runner synchronizes latest changes from main for auditor roles, identifies the active role and target files, executes corresponding role linters and Bazel type check rules, formats clean diagnostic outputs, and returns verification exit status. [realize_check_files]
- In submit, the runner delegates target submission to the submission coordinator and clears pending work upon acceptance. [realize_submit]
- In blame, the runner delegates critique attribution to the attribution coordinator and clears pending work upon acceptance. [realize_blame]
- In fail, the runner delegates failure diagnostics to the attribution coordinator and clears pending work upon acceptance. [realize_fail]
- In coverage, the runner delegates statement coverage evaluation to the coverage evaluator using local workspace files when present and formats diagnostic reports. [realize_coverage]
- In commission, decommission, and refresh-sys, the runner coordinates provisioning, registry lookup, and synchronizer refresh. [realize_lifecycle]

### Woven Contracts

- When running get_work, the runner invokes synchronizer pull and refresh, queries work manager queue, writes pending targets, and prints formatted instructions. [realize_get_work, workspace_sync: [pull_inbound_updates, refresh_system_configs], workspace_work: [compute_role_work_queue_targets, set_pending_work_targets]]
- When running submit, the runner invokes submission coordinator, prints outcome, and updates pending work buffer. [realize_submit, control_submit: [submit_target_file_rule], workspace_work: [remove_pending_target_path]]
- When running blame, the runner invokes attribution coordinator, prints outcome, and updates pending work buffer. [realize_blame, control_attribution: [blame_culprit_file_rule], workspace_work: [remove_pending_target_path]]
- When running fail, the runner invokes attribution coordinator, prints outcome, and updates pending work buffer. [realize_fail, control_attribution: [fail_target_file_rule], workspace_work: [remove_pending_target_path]]

## Grounding

### Knowledge Provisions

- Cleanroom role workspace CLI entrypoint execution implementation. [workspace_tool_realization]

### Knowledge Requirements

- Active workspace registry and repository root discovery.
  - Grounded: [workspace_registry: [workspace_registry_service]]
- Workspace provisioning and decommissioning capabilities.
  - Grounded: [workspace_provision: [workspace_provision_service]]
- Inbound pulling and system file refresh capabilities.
  - Grounded: [workspace_sync: [workspace_sync_service]]
- Work queue evaluation and pending target tracking capabilities.
  - Grounded: [workspace_work: [workspace_work_discovery_service, workspace_pending_work_tracking]]
- Target submission validation and in-band metadata stamping.
  - Grounded: [control_submit: [submission_service]]
- Blame attribution and failure recording capabilities.
  - Grounded: [control_attribution: [attribution_service]]
- Statement test coverage evaluation and diagnostic reporting.
  - Grounded: [tool_coverage: [coverage_evaluation_service]]
