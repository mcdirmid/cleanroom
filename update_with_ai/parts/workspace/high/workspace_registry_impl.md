<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: 9f5c48591fbf
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# workspace_registry_impl implementation component

imports: agent_session, cleanroom_files_ext
implements: workspace_registry

## Purpose

The workspace_registry_impl implementation component realizes role configuration resolution, path sanitization, and persistent workspace registration in the workspaces registry file designated by cleanroom_files_ext.

Reliable multi-role orchestration depends on atomic registry file updates and deterministic workspace naming conventions across platforms. Incomplete role resolution or corrupted registry records lead to orphaned role trees, stale lock files, and race conditions during simultaneous provisioning. The workspace_registry_impl implementation component resolves role definitions dynamically from declarative role configuration files using TOML parsing (falling back to build files using AST evaluation when TOML is absent), normalizes role identifiers, computes directory hashes, and performs atomic JSON registry serialization with file locking.

**Out of scope:** The workspace_registry_impl implementation component does not provision directory contents, synchronize git state, or evaluate task dirty status; these are handled by other components.

**Delegated:** Cleanroom configuration, registry, and role descriptor file naming contracts are delegated to cleanroom_files_ext; session tier management is delegated to agent_session.

## Types and Behavior

The workspace registry discovers the canonical repository root by ascending the directory tree until it locates git metadata directories or canonical Cleanroom configuration files, ignoring the projected role workspace directories that carry a role descriptor. From within an isolated role workspace, the registry inspects role metadata descriptors or matches sibling workspace conventions, and it falls back to the ambient process working directory when no indicator is present.

The workspace registry resolves a role definition by loading the declarative role configuration files of the repository root or methodology directory, falling back to parsing the role declarations of the repository build file by abstract syntax tree evaluation when no role configuration file exists. Resolution extracts every declared role attribute, derives writable file patterns from source patterns, derives read-only file patterns from role dependencies and star role dependencies, and computes audit tags for auditor roles that carry no primary source artifact. Resolution of an unknown or undeclared role fails fast by raising an explicit error without a synthetic fallback.

The workspace registry computes a role workspace directory path by combining the parent directory of the repository root with the role name and the directory scope, sanitizing directory delimiters into underscores to produce a collision-free sibling workspace.

The workspace registry reads and writes the active workspace descriptors in its registry file, writing through a temporary staging file so that a concurrent read never observes a partial record. Registering a workspace appends or updates the descriptor in the registry, and unregistering removes the matching workspace directories.
