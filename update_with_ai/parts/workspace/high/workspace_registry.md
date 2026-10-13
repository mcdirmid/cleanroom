<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-10T19:45:00Z
CHANGE: specify methodology-bound and qualified role resolution
CODE_HASH: afb28350e6de
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# workspace_registry interface component

imports: agent_session

## Purpose

The workspace_registry interface component defines data types and operational contracts for resolving role definitions, computing role workspace locations, and recording active workspaces in persistent storage.

Managing multiple directory-scoped and role-specific workspaces requires consistent mapping between role configurations, canonical repository roots, and isolated workspace working trees. Ad-hoc path computation and untracked workspace lifecycles cause directory collisions, orphaned work trees, and conflicting concurrent runs. The workspace_registry interface component establishes standard models for role configuration and active workspace descriptors, providing uniform operations to locate repository roots, sanitize target directory paths, resolve role metadata, and track active workspaces across the system.

**Out of scope:** The workspace_registry interface component does not copy workspace source files, execute test suites, or schedule graph tasks; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *role definition* record encapsulates configuration for an autonomous development role: a *role name*, a *role address* when explicitly targeted, a *guide path*, a starter *template* path when defined, a *template command* when dynamic scaffolding applies, a *source pattern*, *writable file patterns*, *read-only file patterns*, *role dependencies*, *star role dependencies*, *silent role dependencies*, *stub role dependencies*, *silent cross-role dependencies*, *feedback role dependencies*, *active component types*, a *verification template*, a *verification success message*, a *persona*, *workspace files*, *tools*, an *audit tag* when the role performs auditing, and a *task prompt* when custom instructions apply.

A *workspace descriptor* record encapsulates metadata identifying an active role workspace: a *workspace directory*, a *main repository root*, a *directory scope*, a *role definition*, and a *last sync timestamp* recording recent synchronization.

An agent session's *workspace registry* resolves role specifications and tracks commissioned role workspaces.

Role definitions obey three declaration constraints. Feedback role dependencies and star role dependencies are implicitly role dependencies, so neither is declared again under role dependencies, and a dependency is never declared as both a role dependency and a silent role dependency. An auditor role is declared only as a silent role dependency, never as a role dependency, a star role dependency, or a feedback role dependency.

The workspace registry resolves the canonical repository root from the filesystem environment or the current working directory.

The workspace registry resolves a role definition and lists every declared role definition from declarative role configuration files or repository build files, raising an explicit failure when a queried role is undeclared or when a role definition violates a declaration constraint. When resolving an unqualified role definition within a directory scope, the registry discovers the methodology configuration bound to that directory scope or its package hierarchy and loads the role definitions declared by that methodology. When resolving a qualified role address, the registry loads role definitions declared by the addressed package.

The workspace registry computes a deterministic sanitized role workspace directory path from repository roots, role names, and directory scopes, records newly commissioned role workspaces into the persistent workspaces registry, and unregisters decommissioned role workspaces from that registry.

The workspace registry queries and loads every currently active workspace descriptor from the persistent workspaces registry.
