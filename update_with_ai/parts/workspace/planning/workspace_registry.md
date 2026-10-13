<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-13T01:25:00Z
CHANGE: eliminate cleanroom_workspaces.json workspace registry file
CODE_HASH: 5be5ef31a9c8
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# workspace_registry interface component

## Intent

Managing multiple directory-scoped and role-specific workspaces requires consistent mapping between role configurations, canonical repository roots, and isolated workspace working trees. Ad-hoc path computation and untracked workspace lifecycles cause directory collisions, orphaned work trees, and conflicting concurrent runs. The workspace_registry interface component establishes standard models for role configuration and active workspace descriptors, providing uniform operations to locate repository roots, sanitize target directory paths, resolve role metadata, and track active workspaces across the system.

## Factored Contracts

### Typing

- A role definition record encapsulates a role name, a role address when explicitly targeted, a guide path, a starter template path when defined, a template command when dynamic scaffolding applies, a source pattern, writable file patterns, read-only file patterns, role dependencies, star role dependencies, silent role dependencies, stub role dependencies, silent cross-role dependencies, feedback role dependencies, active component types, a verification template, a verification success message, a persona, workspace files, tools, an audit tag when the role performs auditing, and a task prompt when custom instructions apply.
- A workspace descriptor record encapsulates a workspace directory, a main repository root, a directory scope, a role definition, and a last sync timestamp recording recent synchronization.
- An agent session's workspace registry resolves role specifications and tracks commissioned role workspaces.

### Contracts

- The workspace registry resolves the canonical repository root from the filesystem environment or the current working directory. [discover_repo_root]
- The workspace registry resolves role definitions dynamically from repository role configuration files or build files. [resolve_role_definition]
- The workspace registry lists all declared role definitions from repository role configuration files or build files. [list_all_role_definitions]
- The workspace registry raises an explicit failure when a queried role is undeclared or violates a declaration constraint. [fail_on_undeclared_or_invalid_role]
- When resolving an unqualified role definition within a directory scope, the workspace registry discovers the methodology configuration bound to that directory scope or its package hierarchy and loads the role definitions that methodology declares. [resolve_unqualified_role_via_methodology]
- When resolving a qualified role address, the workspace registry loads the role definitions declared by the addressed package. [resolve_qualified_role_address]
- The workspace registry rejects role definitions containing redundant role dependency declarations. [reject_redundant_role_dependencies]
- The workspace registry rejects role definitions declaring a dependency as a role dependency and a silent role dependency. [reject_conflicting_silent_role_dependencies]
- The workspace registry rejects role definitions declaring an auditor role in role dependencies, star role dependencies, or feedback role dependencies. [reject_auditor_role_dependencies]
- The workspace registry computes sanitized workspace directory paths for role and directory scope. [compute_workspace_directory_path]
- The workspace registry records workspace descriptors into active registry tracking. [record_workspace_descriptor]
- The workspace registry unregisters workspace descriptors from active registry tracking. [unregister_workspace_descriptor]
- The workspace registry loads all active workspace descriptors from provisioned role workspaces. [load_active_workspace_descriptors]

### Woven Contracts

- When resolving a role workspace location, the registry discovers the canonical repository root and computes a collision-free workspace path matching the role name and directory scope. [discover_repo_root, compute_workspace_directory_path]
- When resolving or listing role configurations, the registry loads role definitions dynamically from repository role configuration files or build files, resolving unqualified roles through their bound methodology and qualified role addresses through the addressed package, rejecting configurations with redundant role dependencies, conflicting silent role dependencies, or non-silent auditor role dependencies. [resolve_role_definition, list_all_role_definitions, resolve_unqualified_role_via_methodology, resolve_qualified_role_address, reject_redundant_role_dependencies, reject_conflicting_silent_role_dependencies, reject_auditor_role_dependencies]
- When registering a newly commissioned workspace, the registry records the workspace descriptor into active tracking. [record_workspace_descriptor, load_active_workspace_descriptors]
- When decommissioning an active workspace, the registry removes the matching workspace descriptor from active tracking. [unregister_workspace_descriptor, load_active_workspace_descriptors]

## Grounding

### Knowledge Provisions

- Repository root discovery and path sanitization capabilities. [workspace_path_resolution]
- Role definition resolution and active registry management services. [workspace_registry_service]

### Knowledge Requirements

- Discovery of repository roots and workspace paths on the filesystem.
  - Deferred: Provided by workspace registry implementation.
- Discovery and tracking of active role workspaces.
  - Deferred: Provided by workspace registry implementation.
