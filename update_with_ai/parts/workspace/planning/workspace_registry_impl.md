<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: b5fd06abb413
-->

# workspace_registry_impl implementation component

imports: agent_session
implements: workspace_registry

## Intent

Reliable multi-role orchestration depends on atomic registry file updates and deterministic workspace naming conventions across platforms. Incomplete role resolution or corrupted registry records lead to orphaned role trees, stale lock files, and race conditions during simultaneous provisioning. The workspace_registry_impl implementation component resolves standard role templates (including high, planning, low, lib, test, qa, and coverage roles), normalizes role identifiers, computes directory hashes, and performs atomic JSON registry serialization with file locking.

## Factored Contracts

### Contracts

- The workspace registry searches ancestor directories for MODULE.bazel or .git markers (distinguishing canonical repositories from projected role workspaces) to locate the canonical repository root. [search_ancestor_markers]
- The workspace registry maps standard Cleanroom role names to built-in file patterns and audit tags. [map_standard_role_patterns]
- The workspace registry normalizes role address strings into canonical role names. [normalize_role_identifier]
- The workspace registry replaces directory separator characters with underscores to construct workspace folder names. [sanitize_directory_folder_name]
- The workspace registry writes JSON descriptors atomically to .cleanroom_workspaces.json using temporary sibling files. [write_json_registry_atomically]
- The workspace registry deserializes JSON descriptors from .cleanroom_workspaces.json into workspace descriptors. [read_json_registry_descriptors]

### Woven Contracts

- When discovering repository roots, the registry searches ancestor markers and falls back to ambient working directories if markers are absent. [search_ancestor_markers, workspace_registry: [discover_repo_root]]
- When resolving role definitions, the registry normalizes identifiers and maps standard role patterns. [normalize_role_identifier, map_standard_role_patterns, workspace_registry: [resolve_standard_role_definition]]
- When computing workspace paths, the registry combines sanitized directory names with parent projects roots. [sanitize_directory_folder_name, workspace_registry: [compute_workspace_directory_path]]
- When recording or unregistering workspaces, the registry reads existing descriptors, updates the collection, and writes the JSON file atomically. [read_json_registry_descriptors, write_json_registry_atomically, workspace_registry: [record_workspace_descriptor, unregister_workspace_descriptor]]

## Grounding

### Knowledge Provisions

- Root marker search and sanitized folder generation mechanics. [path_sanitization_mechanics]
- Atomic JSON registry serialization and role pattern mapping logic. [registry_serialization_logic]

### Inherited Deferred Requirements

- Discovery of repository roots and workspace paths on the filesystem.
  - Grounded: [path_sanitization_mechanics]
- Serialization and deserialization of the persistent workspace registry file.
  - Grounded: [registry_serialization_logic]

### Knowledge Requirements

- Reading and writing files on the local filesystem.
  - Grounded: [registry_serialization_logic, path_sanitization_mechanics]
