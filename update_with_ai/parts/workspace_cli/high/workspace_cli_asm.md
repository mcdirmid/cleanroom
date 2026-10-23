# workspace_cli_asm assembly component

assembles: coverage_impl, check_impl, commands_impl, dirtiness_impl, pending_impl, cli_tool_impl, work_impl
imports: session, cleanroom_files_ext, attribution, submit, work_scheduler, dag_storage, src_metadata, provision, role_registry, sync
implements: coverage, check, commands, dirtiness, pending, cli_tool, work

## Purpose

The workspace_cli_asm assembly component aggregates tool, inspection, and workspace execution services, including module statement test coverage evaluation, role workspace command runner execution, and work queue discovery, into the unified tools package.

Cleanroom role workspaces and developer CLI commands require standard access to testing, coverage, work queue evaluation, and analysis tools through configured lifecycle dependencies. The workspace_cli_asm assembly component initializes constituent services and registers singleton implementations with the session lifecycle registry.

**Out of scope:** The workspace_cli_asm assembly component does not implement individual evaluation logic, execute coverage measurements, or modify source files; these are handled by other components.

## Types and Behavior

The workspace_cli_asm assembly component aggregates the implementations of the tool coverage, workspace tool, and workspace work interfaces, providing a unified assembly for role workspace tool execution, work queue discovery, and module coverage evaluation.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:57Z
LAST_CHANGED: 2026-10-11T04:09:45Z
CHANGE: Removed the agent_session import: it was contributed solely by coverage_impl, which is now system-tier, and is no longer imported by any constituent.
SPEC_QA_AUDIT: 2026-10-15T19:43:57Z
-->
