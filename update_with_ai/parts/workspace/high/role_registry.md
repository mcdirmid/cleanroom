# role_registry interface component

imports: session, roles

## Purpose

The role_registry interface component defines data types and operational contracts for computing role workspace locations and tracking active role workspaces.

Managing multiple directory-scoped and role-specific workspaces requires consistent mapping between role configurations, canonical repository roots, and isolated workspace working trees. Ad-hoc path computation and untracked workspace lifecycles cause directory collisions, orphaned work trees, and conflicting concurrent runs. The role_registry interface component establishes standard models for active workspace descriptors, providing uniform operations to locate repository roots, sanitize target directory paths, resolve role metadata through role services, and track active workspaces across the system.

**Out of scope:** The role_registry interface component does not copy workspace source files, execute test suites, or schedule graph tasks; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session. Role configuration resolution and validation are delegated to roles.

## Types and Behavior

A *workspace descriptor* record encapsulates metadata identifying an active role workspace: a *workspace directory*, a *main repository root*, a *directory scope*, a role definition, and a *last sync timestamp* recording recent synchronization.

An agent session's *workspace registry* resolves role specifications and tracks commissioned role workspaces.

The workspace registry resolves the canonical repository root from the filesystem environment or the current working directory.

The workspace registry resolves a role definition and lists every declared role definition through role resolution services.

The workspace registry computes a deterministic sanitized role workspace directory path from repository roots, role names, and directory scopes, records newly commissioned role workspaces into active registry tracking, and unregisters decommissioned role workspaces.

The workspace registry discovers and loads active workspace descriptors by inspecting provisioned role workspace directories carrying role metadata descriptors.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T18:45:00Z
CHANGE: Delegate role configuration resolution to roles
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
