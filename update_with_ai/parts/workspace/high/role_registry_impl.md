# role_registry_impl implementation component

imports: session, cleanroom_files_ext, roles
implements: role_registry

## Purpose

The role_registry_impl implementation component realizes path sanitization, role delegation, and active workspace tracking and discovery without central registry files.

Reliable multi-role orchestration depends on clean workspace discovery and deterministic workspace naming conventions across platforms. Incomplete role resolution or corrupted registry records lead to orphaned role trees, stale lock files, and race conditions during simultaneous provisioning. The role_registry_impl implementation component coordinates role resolution through dedicated role services, normalizes role workspace identifiers, and tracks commissioned workspaces.

**Out of scope:** The role_registry_impl implementation component does not provision directory contents, synchronize git state, or evaluate task dirty status; these are handled by other components.

**Delegated:** Cleanroom configuration and role descriptor file naming contracts are delegated to cleanroom_files_ext; session tier management is delegated to agent_session; role configuration resolution and validation are delegated to roles.

## Types and Behavior

The workspace registry discovers the canonical repository root by ascending the directory tree until it locates git metadata directories or canonical Cleanroom configuration files, ignoring the projected role workspace directories that carry a role descriptor. From within an isolated role workspace, the registry derives the canonical repository root by matching sibling workspace conventions (`../../<workspace-short-name>`) or environment overrides without inspecting host paths from role metadata descriptors, and it falls back to the ambient process working directory when no indicator is present.

The workspace registry resolves role definitions and lists all declared roles by delegating to role resolution services.

The workspace registry computes a role workspace directory path by combining the parent directory of the repository root with the role name and the directory scope, sanitizing directory delimiters into underscores to produce a collision-free sibling workspace.

The workspace registry tracks active workspace descriptors in memory and discovers provisioned workspaces across the role workspaces directory by reading each workspace's role metadata descriptor. Registering a workspace records the descriptor in memory, and unregistering removes the matching workspace descriptor.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-14T18:45:00Z
CHANGE: Delegate role configuration resolution to roles
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->
