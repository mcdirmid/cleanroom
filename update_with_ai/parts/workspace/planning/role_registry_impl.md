# role_registry_impl implementation component

## Intent

Reliable multi-role orchestration depends on deterministic workspace naming conventions and clean workspace discovery across platforms. Incomplete role resolution leads to orphaned role trees and race conditions during simultaneous provisioning. The role_registry_impl implementation component coordinates role resolution through dedicated role services, normalizes workspace identifiers, and tracks active role workspaces.

## Factored Contracts

### Contracts

- The workspace registry searches ancestor directories for Cleanroom configuration files or .git markers (distinguishing canonical repositories from projected role workspaces) to locate the canonical repository root. [search_ancestor_markers]
- From within an isolated role workspace, the workspace registry matches sibling workspace conventions to resolve the canonical repository root without inspecting host paths from role descriptors. [match_sibling_workspace_conventions]
- The workspace registry falls back to the ambient process working directory when no repository indicator is present. [fallback_to_ambient_working_directory]
- The workspace registry delegates role definition resolution and role listing to role resolution services. [delegate_role_resolution]
- The workspace registry replaces directory separator characters with underscores to construct workspace folder names. [sanitize_directory_folder_name]
- The workspace registry records workspace descriptors in active session memory. [record_in_memory_descriptor]
- The workspace registry discovers active role workspace descriptors from provisioned role metadata descriptors. [discover_active_workspace_descriptors]

### Woven Contracts

- When discovering repository roots, the registry searches ancestor markers, matches sibling workspace conventions from within a role workspace, and falls back to ambient working directories if no indicator is present. [search_ancestor_markers, match_sibling_workspace_conventions, fallback_to_ambient_working_directory, role_registry: [discover_repo_root]]
- When resolving or listing role definitions, the registry delegates to role resolution services. [delegate_role_resolution, role_registry: [resolve_role_definition, list_all_role_definitions]]
- When computing workspace paths, the registry combines sanitized directory names with parent projects roots. [sanitize_directory_folder_name, role_registry: [compute_workspace_directory_path]]
- When recording or unregistering workspaces, the registry updates the in-memory descriptor collection and synchronizes role metadata. [record_in_memory_descriptor, role_registry: [record_workspace_descriptor, unregister_workspace_descriptor]]
- When loading active workspaces, the registry discovers active descriptors by inspecting role metadata descriptors in provisioned role workspaces. [discover_active_workspace_descriptors, role_registry: [load_active_workspace_descriptors]]

## Grounding

### Knowledge Provisions

- Root marker search and sanitized folder generation mechanics. [path_sanitization_mechanics]
- Active workspace descriptor tracking and role metadata discovery logic. [workspace_discovery_logic]

### Inherited Deferred Requirements

- Role definition resolution and validation.
  - Grounded: [roles: [role_resolution_service]]
- Discovery of repository roots and workspace paths on the filesystem.
  - Grounded: [path_sanitization_mechanics]
- Discovery and tracking of active role workspaces.
  - Grounded: [workspace_discovery_logic, cleanroom_files_ext: [cleanroom_configuration_schema]]

### Knowledge Requirements

- Reading and writing files on the local filesystem.
  - Grounded: [workspace_discovery_logic, path_sanitization_mechanics]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T18:45:00Z
CHANGE: Delegate role configuration resolution to roles
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
