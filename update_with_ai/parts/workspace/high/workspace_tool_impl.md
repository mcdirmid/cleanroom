<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:03Z
LAST_CHANGED: 2026-10-11T16:00:00Z
CHANGE: gate submit on role verification checks and support verification bypass
CODE_HASH: fed7fdd41c82
SPEC_QA_AUDIT: 2026-10-11T22:09:03Z
-->

# workspace_tool_impl implementation component

imports: agent_session, workspace_registry, workspace_provision, workspace_sync, workspace_work, control_submit, control_attribution, tool_coverage
implements: workspace_tool

## Purpose

The workspace_tool_impl implementation component realizes the workspace tool runner for cleanroom role workspace CLI execution and argument parsing.

Command-line subagents in Cleanroom workspaces require a robust entrypoint that parses subcommands, synchronizes files from canonical main workspaces, validates inputs, and triggers appropriate domain coordinators. The workspace_tool_impl implementation component consolidates argument parsing, console output rendering, and execution workflows into a singleton runner operating within the agent session lifecycle tier.

**Out of scope:** The workspace_tool_impl implementation component does not implement custom test runners or low-level file metadata storage; these are handled by other components.

**Delegated:** Session tier scoping is delegated to agent_session; active workspace discovery and repository root resolution are delegated to workspace_registry; workspace commissioning is delegated to workspace_provision; file harvesting, system refresh, and pulling are delegated to workspace_sync; queue evaluation and pending target tracking are delegated to workspace_work; target submission gating and code hash validation are delegated to control_submit; defect blame attribution and failure marking are delegated to control_attribution; statement test coverage analysis is delegated to tool_coverage.

## Types and Behavior

The workspace tool runner realization implements command execution, command-line argument parsing, and diagnostic formatting.

The realization parses command-line arguments across the work, check files, submit, blame, feedback, fail, coverage, commission, and refresh system subcommands.

The realization:

- Pulls inbound changes from the canonical main workspace during work execution, verifies whether prior dirty targets remain pending in the role workspace, evaluates ready and blocked items from the work manager, records pending targets, and formats actionable next steps.

- Resolves the active role and target files during check files execution, regenerates a missing target file from its starter template for roles that declare source patterns and upstream dependencies before verification, executes the corresponding static linting, type-checking, or test rules, formats clean diagnostic outcomes, and returns the verification exit status.

- Evaluates role verification checks on the target file during submit execution, rejecting submission when verification fails unless bypassed, delegates file validation and metadata stamping to the submission coordinator, reflects stamped files into the role workspace, appends submission records to the cleanroom log, and clears the target from pending work on success.

- Verifies single-paragraph critique constraints during blame and feedback execution, delegates attribution to the attribution coordinator, appends blame records to the cleanroom log, and clears the target from pending work on success.

- Delegates failure tagging and diagnostic recording to the attribution coordinator during fail execution, clearing the target from pending work on success.

- Delegates statement coverage evaluation to the coverage evaluator during coverage execution, using the local workspace files when present, and formats diagnostic span reports.

- Delegates workspace provisioning, registration, and system synchronization across the active role workspaces during commission and refresh system execution.
