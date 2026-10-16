<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:57Z
LAST_CHANGED: 2026-10-11T04:09:45Z
CHANGE: Removed the agent_session import: it was contributed solely by tool_coverage_impl, which is now system-tier, and is no longer imported by any constituent.
CODE_HASH: 45d5b7ccd58b
SPEC_QA_AUDIT: 2026-10-15T19:43:57Z
-->

# tools_asm assembly component

assembles: tool_coverage_impl, workspace_check_impl, workspace_commands_impl, workspace_dirtiness_impl, workspace_pending_impl, workspace_tool_impl, workspace_work_impl
imports: agent_session, cleanroom_files_ext, control_attribution, control_submit, control_work_scheduler, dag_storage, src_metadata, workspace_provision, workspace_registry, workspace_sync
implements: tool_coverage, workspace_check, workspace_commands, workspace_dirtiness, workspace_pending, workspace_tool, workspace_work

## Purpose

The tools_asm assembly component aggregates tool, inspection, and workspace execution services, including module statement test coverage evaluation, role workspace command runner execution, and work queue discovery, into the unified tools package.

Cleanroom role workspaces and developer CLI commands require standard access to testing, coverage, work queue evaluation, and analysis tools through configured lifecycle dependencies. The tools_asm assembly component initializes constituent services and registers singleton implementations with the session lifecycle registry.

**Out of scope:** The tools_asm assembly component does not implement individual evaluation logic, execute coverage measurements, or modify source files; these are handled by other components.

## Types and Behavior

The tools_asm assembly component aggregates the implementations of the tool coverage, workspace tool, and workspace work interfaces, providing a unified assembly for role workspace tool execution, work queue discovery, and module coverage evaluation.
