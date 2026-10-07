<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: b196e83dec27
-->

# workspace_registry interface component

imports: agent_session

## Intent

Managing multiple directory-scoped and role-specific workspaces requires consistent mapping between role configurations, canonical repository roots, and isolated workspace working trees. Ad-hoc path computation and untracked workspace lifecycles cause directory collisions, orphaned work trees, and conflicting concurrent runs. The workspace_registry interface component establishes standard models for role configuration and active workspace descriptors, providing uniform operations to locate repository roots, sanitize target directory paths, resolve role metadata, and track active workspaces across the system.

## Factored Contracts

### Typing

- A role definition record encapsulates a role name, an optional role address, a guide path, a sequence of writable file patterns, a sequence of read-only file patterns, a sequence of feedback role dependencies, an optional audit tag, and an optional task prompt.
- A workspace descriptor record encapsulates a workspace directory, a main repository root, a directory scope, a role definition, and an optional last sync timestamp.
- A workspace registry operates within the agent session lifecycle tier.

### Contracts

- The workspace registry discovers the canonical repository root by ascending directory trees. [discover_repo_root]
- The workspace registry resolves role definitions matching standard Cleanroom role names. [resolve_standard_role_definition]
- The workspace registry computes sanitized workspace directory paths for role and directory scope. [compute_workspace_directory_path]
- The workspace registry records workspace descriptors into the persistent workspaces registry file. [record_workspace_descriptor]
- The workspace registry unregisters workspace descriptors from the persistent workspaces registry file. [unregister_workspace_descriptor]
- The workspace registry loads all active workspace descriptors from the persistent workspaces registry file. [load_active_workspace_descriptors]

### Woven Contracts

- When resolving a role workspace location, the registry discovers the canonical repository root and computes a collision-free workspace path matching the role name and directory scope. [discover_repo_root, compute_workspace_directory_path]
- When registering a newly commissioned workspace, the registry appends the workspace descriptor to the persistent registry file. [record_workspace_descriptor, load_active_workspace_descriptors]
- When decommissioning an active workspace, the registry removes the matching workspace descriptor from the persistent registry file. [unregister_workspace_descriptor, load_active_workspace_descriptors]

## Grounding

### Knowledge Provisions

- Repository root discovery and path sanitization capabilities. [workspace_path_resolution]
- Role definition resolution and persistent registry management services. [workspace_registry_service]

### Knowledge Requirements

- Discovery of repository roots and workspace paths on the filesystem.
  - Deferred: Provided by workspace registry implementation.
- Serialization and deserialization of the persistent workspace registry file.
  - Deferred: Provided by workspace registry implementation.
