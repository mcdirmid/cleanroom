<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T18:45:00Z
CHANGE: Delegate role configuration resolution to workspace_roles
CODE_HASH: 3831f687bd74
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# workspace_registry interface component

## Intent

Managing multiple directory-scoped and role-specific workspaces requires consistent mapping between role configurations, canonical repository roots, and isolated workspace working trees. Ad-hoc path computation and untracked workspace lifecycles cause directory collisions, orphaned work trees, and conflicting concurrent runs. The workspace_registry interface component establishes standard models for active workspace descriptors, providing uniform operations to locate repository roots, sanitize target directory paths, resolve role metadata through role services, and track active workspaces across the system.

## Factored Contracts

### Typing

- A workspace descriptor record encapsulates a workspace directory, a main repository root, a directory scope, a role definition, and a last sync timestamp recording recent synchronization.
- An agent session's workspace registry resolves role specifications and tracks commissioned role workspaces.

### Contracts

- The workspace registry resolves the canonical repository root from the filesystem environment or the current working directory. [discover_repo_root]
- The workspace registry resolves role definitions through role resolution services. [resolve_role_definition]
- The workspace registry lists all declared role definitions through role resolution services. [list_all_role_definitions]
- The workspace registry computes sanitized workspace directory paths for role and directory scope. [compute_workspace_directory_path]
- The workspace registry records workspace descriptors into active registry tracking. [record_workspace_descriptor]
- The workspace registry unregisters workspace descriptors from active registry tracking. [unregister_workspace_descriptor]
- The workspace registry loads all active workspace descriptors from provisioned role workspaces. [load_active_workspace_descriptors]

### Woven Contracts

- When resolving a role workspace location, the registry discovers the canonical repository root and computes a collision-free workspace path matching the role name and directory scope. [discover_repo_root, compute_workspace_directory_path]
- When resolving or listing role configurations, the registry delegates resolution and listing to role resolution services. [resolve_role_definition, list_all_role_definitions]
- When registering a newly commissioned workspace, the registry records the workspace descriptor into active tracking. [record_workspace_descriptor, load_active_workspace_descriptors]
- When decommissioning an active workspace, the registry removes the matching workspace descriptor from active tracking. [unregister_workspace_descriptor, load_active_workspace_descriptors]

## Grounding

### Knowledge Provisions

- Repository root discovery and path sanitization capabilities. [workspace_path_resolution]
- Workspace registry management services. [workspace_registry_service]

### Knowledge Requirements

- Role definition resolution and validation.
  - Deferred: [workspace_roles: [role_resolution_service]]
- Discovery of repository roots and workspace paths on the filesystem.
  - Deferred: Provided by workspace registry implementation.
- Discovery and tracking of active role workspaces.
  - Deferred: Provided by workspace registry implementation.
