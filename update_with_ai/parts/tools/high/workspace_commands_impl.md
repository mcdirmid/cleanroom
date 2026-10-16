<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:50:00Z
CHANGE: Define workspace_commands_impl implementation specification
CODE_HASH: 84f9b696bce7
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# workspace_commands_impl implementation component

imports: agent_session, cleanroom_files_ext, control_attribution, control_submit, tool_coverage, workspace_check, workspace_commands, workspace_pending, workspace_provision, workspace_registry, workspace_sync
implements: workspace_commands

## Purpose

The workspace_commands_impl implementation component realizes substantive command execution workflows for Cleanroom role workspaces, including work evaluation, verification, submission, attribution, coverage, commissioning, and system refresh.

Operating command-line subagents in isolated workspaces requires domain logic that synchronizes working trees with canonical repositories, validates file boundaries, invokes submission coordinators, attributes defect critiques, measures statement test coverage, and provisions role workspaces. The workspace_commands_impl implementation component consolidates these operational workflows into a singleton command handler operating within the agent session lifecycle tier.

**Out of scope:** The workspace_commands_impl implementation component does not parse command-line argument strings; argument parsing is handled by workspace_tool_impl.

**Delegated:** Session tier scoping is delegated to agent_session; workspace discovery and role definitions are delegated to workspace_registry; workspace commissioning is delegated to workspace_provision; file harvesting, system refresh, and pulling are delegated to workspace_sync; work discovery and file verification runners are delegated to workspace_check; pending work buffer tracking is delegated to workspace_pending; cleanroom log file naming conventions are delegated to cleanroom_files_ext; target submission gating and code hash validation are delegated to control_submit; defect blame attribution and failure marking are delegated to control_attribution; statement test coverage analysis is delegated to tool_coverage.

## Types and Behavior

The workspace command handler realization implements the domain workflows for all Cleanroom role workspace operations.

The realization:

- Delegates work queue discovery and actionable task presentation in the local role workspace to the workspace checker.

- Delegates file verification checks, linters, and type checking to the workspace checker.

- Evaluates role verification checks on the target file during submit execution, rejecting submission when verification fails unless bypassed, delegates file validation and metadata stamping to the submission coordinator, reflects stamped files into the role workspace, appends submission records to the cleanroom log, and clears the target from pending work on success.

- Verifies single-paragraph critique constraints during blame and feedback execution, delegates attribution to the attribution coordinator, appends blame records to the cleanroom log, and clears the target from pending work on success.

- Delegates failure tagging and diagnostic recording to the attribution coordinator during fail execution, clearing the target from pending work on success.

- Delegates statement coverage evaluation to the coverage evaluator during coverage execution, using local workspace files when present, and formats diagnostic span reports.

- Delegates workspace provisioning, registration, and system synchronization across active role workspaces during commission and refresh system execution, dynamically discovering or requiring the directory scope without hardcoded defaults, mapping directory scope arguments when provisioning across all declared roles, supporting resetting stale work buffers and stamping model execution profiles into role descriptors, and supporting provisioning across all declared roles within a directory scope when requested.
