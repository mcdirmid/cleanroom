# commands_impl implementation component

## Intent

The commands_impl implementation component realizes substantive command execution workflows for Autofab role workspaces, including work evaluation, verification, submission, attribution, coverage, commissioning, and system refresh. It encapsulates domain logic that synchronizes working trees with canonical repositories, validates file boundaries, invokes submission coordinators, attributes defect critiques, validates coverage-based blame attribution, measures statement test coverage, and provisions role workspaces within the agent session lifecycle tier.

## Factored Contracts

### Typing

- The workspace command handler realization implements WorkspaceCommandHandler and operates in agent_session.

### Contracts

- In run_get_work and run_check_files, the handler delegates work discovery and file verification directly to the workspace checker. [delegate_check_commands]
- In run_submit, the handler evaluates role verification checks on the target unless bypassed, enforcing that modified targets have been verified via check_files since modification; if staged blame exists in the workspace buffer for a failing target, it commits all staged blame items to their culprits, marks culprits dirty, appends blame records to the Autofab log, clears the staged blame buffer, and clears the target from pending work; if manual submission is attempted without preceding blame in auditor roles, it rejects submission; if verification fails without staged blame, it rejects submission; otherwise it delegates target submission to the submission coordinator, appends the submission record to the Autofab log, and clears pending work upon acceptance. [realize_submit]
- In run_blame and run_feedback, the handler sanitizes critique explanations into a single continuous paragraph, enforces that modified workspace targets have been verified via check_files since modification, validates caller role feedback delivery permissions against the union of direct feedback role dependencies (`feedback_role_deps`) and cross-unit star feedback role dependencies (`star_feedback_role_deps`), validates the structured blame tuple (specification slug grounding in low-level specifications, violation code taxonomy, noun phrase facet constraints, and zero-entropy symbol embargo) when the structured blame experiment is active, validates blame attribution against open coverage spans in the coverage status buffer (rejecting identical repeated blames against identical span sets while permitting test-directed blame for contracted postconditions and operational errors), stages the blame item into the workspace staged blame buffer, and notifies the caller to stage additional blame or commit staged blame via submit. [realize_blame]
- In run_reject, the handler enforces that the target file has not been modified since receiving feedback, verifies active feedback exists in the file header, removes the feedback header block from the target file, records the rejection contest reason into the workspace blame buffer and Autofab log, clears the target from pending work, and emits a post-reject round conclusion directive instructing the worker to run bin/get_work. [realize_reject]
- In run_fail, the handler enforces that modified targets have been verified via check_files since modification, delegates failure diagnostics to the attribution coordinator, and clears matching or single pending workspace work upon acceptance. [realize_fail]
- In run_coverage, the handler delegates statement coverage evaluation to the coverage evaluator using local workspace files when present and formats diagnostic reports. [realize_coverage]
- In run_commission and run_refresh_sys, the handler coordinates provisioning, registry lookup, and synchronizer refresh across single roles or all declared roles within a directory scope, mapping positional arguments to directory scope when all roles are requested, requiring or discovering scope without hardcoded defaults, and supporting resetting stale work buffers and stamping model execution profiles. [realize_lifecycle]

### Woven Contracts

- When executing get_work or check_files, the handler delegates to the workspace checker. [delegate_check_commands, commands: [execute_get_work_command, execute_check_files_command], check: [run_workspace_get_work, run_workspace_check_files]]
- When executing submit, the handler evaluates role verification checks, rejects failing targets, coordinates file submission mutations, and clears pending work buffers upon acceptance. [realize_submit, commands: [execute_submit_command], submit: [execute_file_submission_mutation], pending: [remove_pending_target_path]]
- When executing blame or feedback, the handler sanitizes critique rules, validates blame targets against open coverage deficit spans, stages blame items into the staged blame buffer, and prompts for additional blame or submission. [realize_blame, commands: [execute_blame_command]]
- When executing reject, the handler verifies unmodified code, scrubs feedback headers, records rejections, and clears pending work buffers upon acceptance. [realize_reject, commands: [execute_reject_command], pending: [remove_pending_target_path]]
- When executing fail, the handler coordinates failure mutations and clears pending work buffers upon acceptance. [realize_fail, commands: [execute_fail_command], attribution: [execute_file_failure_mutation], pending: [remove_pending_target_path]]
- When executing coverage, the handler evaluates statement coverage and formats reports. [realize_coverage, commands: [execute_coverage_command], coverage: [evaluate_module_coverage, format_coverage_report]]
- When executing commission or refresh-sys, the handler coordinates provisioning and system file refresh across active role workspaces. [realize_lifecycle, commands: [execute_commission_command, execute_refresh_sys_command], provision: [commission_role_workspace], sync: [refresh_system_files_into_workspace], role_registry: [resolve_role_definition, compute_workspace_directory_path]]

## Grounding

### Knowledge Provisions

- Workspace domain command workflows realization. [workspace_commands_realization]
- Subcommand execution coordination across Autofab subsystems. [workspace_commands_coordination]

### Inherited Deferred Requirements

- Domain execution of workspace commands across Autofab subsystems.
  - Grounded: [workspace_commands_coordination, sync: [workspace_pull_service], check: [workspace_check_service], pending: [workspace_pending_work_tracking], submit: [file_submission_gating_service], attribution: [file_attribution_service], coverage: [coverage_evaluation_service], role_registry: [workspace_registry_service], provision: [workspace_provisioning_service]]

### Knowledge Requirements

- Active workspace registry and repository root discovery.
  - Grounded: [role_registry: [workspace_registry_service]]
- Workspace provisioning capabilities.
  - Grounded: [provision: [workspace_provisioning_service]]
- Inbound upstream file pull and non-parts system refresh services.
  - Grounded: [sync: [workspace_pull_service]]
- Workspace work discovery and file checking command services.
  - Grounded: [check: [workspace_check_service]]
- Pending work buffer state management and dirtiness evaluation services.
  - Grounded: [pending: [workspace_pending_work_tracking, workspace_pending_dirtiness_service]]
- Target submission gating and in-band metadata stamping services.
  - Grounded: [submit: [file_submission_gating_service]]
- File-level blame attribution and failure mutation services.
  - Grounded: [attribution: [file_attribution_service]]
- Module statement coverage evaluation and report generation services.
  - Grounded: [coverage: [coverage_evaluation_service]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T11:00:00Z
LAST_CHANGED: 2026-11-07T10:20:00Z
CHANGE: Realize reject command, stage blame items in buffer, and commit staged blames upon submit with auditor blame requirement
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
