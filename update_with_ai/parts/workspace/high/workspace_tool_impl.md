<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-08T15:45:00Z
CHANGE: clarify check_files template regeneration for regenerable roles
CODE_HASH: 0d7dcc1ed470
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

The workspace tool runner realization implements command execution, CLI argument parsing, and diagnostic formatting.

The realization:

- Parses command-line arguments across get_work, check_files, submit, blame, feedback, fail, coverage, commission, and refresh-sys subcommands.

- In get_work execution, pulls inbound changes from the canonical main workspace, verifies whether prior dirty targets remain pending in the role workspace, evaluates ready and blocked items from the work manager, records pending targets, and formats actionable next steps.

- In check_files execution, resolves active role and target files, regenerates missing target files from starter templates for roles with declared source patterns and upstream dependencies before verification, executes corresponding static linting, type-checking, or test rules, formats clean diagnostic outcomes, and returns verification exit status.

- In submit execution, delegates file validation and metadata stamping to the submission coordinator, reflecting stamped files to the role workspace, appending submission records to the cleanroom log, and clearing the target from pending work on success.

- In blame and feedback execution, verifies single-paragraph critique constraints, delegates attribution to the attribution coordinator, appends blame records to the cleanroom log, and clears the target from pending work on success.

- In fail execution, delegates failure tagging and diagnostic recording to the attribution coordinator, clearing the target from pending work on success.

- In coverage execution, delegates statement coverage evaluation to the coverage evaluator using local workspace files when present and formats diagnostic span reports.

- In commission and refresh-sys execution, delegates workspace provisioning, registration, and system synchronization across active role workspaces.
