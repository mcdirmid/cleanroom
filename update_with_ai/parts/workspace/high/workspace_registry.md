<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: 2c0341918784
-->

# workspace_registry interface component

imports: agent_session

## Purpose

The workspace_registry interface component defines data types and operational contracts for resolving role definitions, computing role workspace locations, and recording active workspaces in persistent storage.

Managing multiple directory-scoped and role-specific workspaces requires consistent mapping between role configurations, canonical repository roots, and isolated workspace working trees. Ad-hoc path computation and untracked workspace lifecycles cause directory collisions, orphaned work trees, and conflicting concurrent runs. The workspace_registry interface component establishes standard models for role configuration and active workspace descriptors, providing uniform operations to locate repository roots, sanitize target directory paths, resolve role metadata, and track active workspaces across the system.

**Out of scope:** The workspace_registry interface component does not copy workspace source files, execute test suites, or schedule graph tasks; these are handled by other components.

## Types and Behavior

A *role definition* record encapsulates configuration for an autonomous development role: a *role name*, an optional *role address*, a *guide path*, an optional *template*, an optional *template command*, a *source pattern*, a sequence of *writable file patterns*, a sequence of *read-only file patterns*, a sequence of *role dependencies*, a sequence of *star role dependencies*, a sequence of *silent role dependencies*, a sequence of *stub role dependencies*, a sequence of *silent cross-role dependencies*, a sequence of *feedback role dependencies*, a sequence of *active component types*, a *verification template*, a *verification success message*, a *persona*, a sequence of *workspace files*, a sequence of *tools*, an optional *audit tag*, and an optional *task prompt*.

A *workspace descriptor* record encapsulates metadata identifying an active role workspace: a *workspace directory*, a *main repository root*, a *directory scope*, a *role definition*, and an optional *last sync timestamp*.

A session's *workspace registry* resolves role specifications and tracks commissioned role workspaces.

The workspace registry:

- Resolves the canonical repository root from the filesystem environment or current working directory.

- Resolves role definitions dynamically from declarative role configuration files (such as cleanroom_python_roles.toml) or repository build files, raising an explicit failure if a queried role is undeclared.

- Lists all declared role definitions from repository role configuration files or build files.

- Computes deterministic, sanitized role workspace directory paths from repository roots, role names, and directory scopes.

- Records newly commissioned role workspaces into the persistent workspaces registry.

- Unregisters decommissioned role workspaces from the persistent workspaces registry.

- Queries and loads all currently active workspace descriptors from the persistent workspaces registry.
