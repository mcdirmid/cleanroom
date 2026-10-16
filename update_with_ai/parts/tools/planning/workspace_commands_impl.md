<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:50:00Z
CHANGE: Define workspace_commands_impl planning specification
CODE_HASH: a5787bf4118c
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# workspace_commands_impl implementation component

## Intent

The workspace_commands_impl implementation component realizes substantive command execution workflows for Cleanroom role workspaces, including work evaluation, verification, submission, attribution, coverage, commissioning, and system refresh. It encapsulates domain logic that synchronizes working trees with canonical repositories, validates file boundaries, invokes submission coordinators, attributes defect critiques, measures statement test coverage, and provisions role workspaces within the agent session lifecycle tier.

## Factored Contracts

### Typing

- The workspace command handler realization implements WorkspaceCommandHandler and operates in agent_session.

### Contracts

- In run_get_work and run_check_files, the handler delegates work discovery and file verification directly to the workspace checker. [delegate_check_commands]
- In run_submit, the handler evaluates role verification checks on the target unless bypassed, rejecting submission when verification fails, delegates target submission to the submission coordinator, appends the submission record to the cleanroom log, and clears pending work upon acceptance. [realize_submit]
- In run_blame and run_feedback, the handler verifies single-paragraph critique constraints, delegates critique attribution to the attribution coordinator, appends the blame record to the cleanroom log, and clears pending work upon acceptance. [realize_blame]
- In run_fail, the handler delegates failure diagnostics to the attribution coordinator and clears pending work upon acceptance. [realize_fail]
- In run_coverage, the handler delegates statement coverage evaluation to the coverage evaluator using local workspace files when present and formats diagnostic reports. [realize_coverage]
- In run_commission and run_refresh_sys, the handler coordinates provisioning, registry lookup, and synchronizer refresh across single roles or all declared roles within a directory scope, mapping positional arguments to directory scope when all roles are requested, requiring or discovering scope without hardcoded defaults, and supporting resetting stale work buffers and stamping model execution profiles. [realize_lifecycle]

### Woven Contracts

- When executing get_work or check_files, the handler delegates to the workspace checker. [delegate_check_commands, workspace_commands: [execute_get_work_command, execute_check_files_command], workspace_check: [run_workspace_get_work, run_workspace_check_files]]
- When executing submit, the handler evaluates role verification checks, rejects failing targets, coordinates file submission mutations, and clears pending work buffers upon acceptance. [realize_submit, workspace_commands: [execute_submit_command], control_submit: [execute_file_submission_mutation], workspace_pending: [remove_pending_target_path]]
- When executing blame or feedback, the handler validates single-paragraph critique rules, coordinates defect blame mutations, and clears pending work buffers upon acceptance. [realize_blame, workspace_commands: [execute_blame_command], control_attribution: [execute_file_blame_mutation], workspace_pending: [remove_pending_target_path]]
- When executing fail, the handler coordinates failure mutations and clears pending work buffers upon acceptance. [realize_fail, workspace_commands: [execute_fail_command], control_attribution: [execute_file_failure_mutation], workspace_pending: [remove_pending_target_path]]
- When executing coverage, the handler evaluates statement coverage and formats reports. [realize_coverage, workspace_commands: [execute_coverage_command], tool_coverage: [evaluate_module_coverage, format_coverage_report]]
- When executing commission or refresh-sys, the handler coordinates provisioning and system file refresh across active role workspaces. [realize_lifecycle, workspace_commands: [execute_commission_command, execute_refresh_sys_command], workspace_provision: [commission_role_workspace], workspace_sync: [refresh_system_files_into_workspace], workspace_registry: [resolve_role_definition, compute_workspace_directory_path]]

## Grounding

### Knowledge Provisions

- Workspace domain command workflows realization. [workspace_commands_realization]
- Subcommand execution coordination across cleanroom subsystems. [workspace_commands_coordination]

### Inherited Deferred Requirements

- Domain execution of workspace commands across cleanroom subsystems.
  - Grounded: [workspace_commands_coordination, workspace_sync: [workspace_pull_service], workspace_check: [workspace_check_service], workspace_pending: [workspace_pending_work_tracking], control_submit: [file_submission_gating_service], control_attribution: [file_attribution_service], tool_coverage: [coverage_evaluation_service], workspace_registry: [workspace_registry_service], workspace_provision: [workspace_provisioning_service]]

### Knowledge Requirements

- Active workspace registry and repository root discovery.
  - Grounded: [workspace_registry: [workspace_registry_service]]
- Workspace provisioning capabilities.
  - Grounded: [workspace_provision: [workspace_provisioning_service]]
- Inbound upstream file pull and non-parts system refresh services.
  - Grounded: [workspace_sync: [workspace_pull_service]]
- Workspace work discovery and file checking command services.
  - Grounded: [workspace_check: [workspace_check_service]]
- Pending work buffer state management and dirtiness evaluation services.
  - Grounded: [workspace_pending: [workspace_pending_work_tracking, workspace_pending_dirtiness_service]]
- Target submission gating and in-band metadata stamping services.
  - Grounded: [control_submit: [file_submission_gating_service]]
- File-level blame attribution and failure mutation services.
  - Grounded: [control_attribution: [file_attribution_service]]
- Module statement coverage evaluation and report generation services.
  - Grounded: [tool_coverage: [coverage_evaluation_service]]
