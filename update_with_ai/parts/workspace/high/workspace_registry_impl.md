<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-13T01:25:00Z
CHANGE: eliminate cleanroom_workspaces.json workspace registry file
CODE_HASH: 9f5c48591fbf
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# workspace_registry_impl implementation component

imports: agent_session, cleanroom_files_ext
implements: workspace_registry

## Purpose

The workspace_registry_impl implementation component realizes role configuration resolution, path sanitization, and active workspace tracking and discovery without central registry files.

Reliable multi-role orchestration depends on clean workspace discovery and deterministic workspace naming conventions across platforms. Incomplete role resolution or corrupted registry records lead to orphaned role trees, stale lock files, and race conditions during simultaneous provisioning. The workspace_registry_impl implementation component resolves role definitions dynamically from declarative role configuration files using TOML parsing (falling back to build files using AST evaluation when TOML is absent), normalizes role identifiers, and tracks commissioned workspaces.

**Out of scope:** The workspace_registry_impl implementation component does not provision directory contents, synchronize git state, or evaluate task dirty status; these are handled by other components.

**Delegated:** Cleanroom configuration and role descriptor file naming contracts are delegated to cleanroom_files_ext; session tier management is delegated to agent_session.

## Types and Behavior

The workspace registry discovers the canonical repository root by ascending the directory tree until it locates git metadata directories or canonical Cleanroom configuration files, ignoring the projected role workspace directories that carry a role descriptor. From within an isolated role workspace, the registry inspects role metadata descriptors or matches sibling workspace conventions, and it falls back to the ambient process working directory when no indicator is present.

The workspace registry resolves a role definition by loading the declarative role configuration files of the repository root or methodology directory, falling back to parsing the role declarations of the repository build file by abstract syntax tree evaluation when no role configuration file exists. Resolution extracts every declared role attribute, derives writable file patterns from source patterns, derives read-only file patterns from role dependencies and star role dependencies, and computes audit tags for auditor roles that carry no primary source artifact. Resolution of an unknown or undeclared role fails fast by raising an explicit error without a synthetic fallback.

The workspace registry computes a role workspace directory path by combining the parent directory of the repository root with the role name and the directory scope, sanitizing directory delimiters into underscores to produce a collision-free sibling workspace.

The workspace registry tracks active workspace descriptors in memory and discovers provisioned workspaces across the role workspaces directory by reading each workspace's role metadata descriptor. Registering a workspace records the descriptor in memory, and unregistering removes the matching workspace descriptor.
