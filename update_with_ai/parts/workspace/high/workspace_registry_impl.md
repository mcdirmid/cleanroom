<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: 5fa7db538162
-->

# workspace_registry_impl implementation component

imports: agent_session, bazel_manifest_ext
implements: workspace_registry

## Purpose

The workspace_registry_impl implementation component realizes role configuration resolution, path sanitization, and persistent workspace registration in `.cleanroom_workspaces.json`.

Reliable multi-role orchestration depends on atomic registry file updates and deterministic workspace naming conventions across platforms. Incomplete role resolution or corrupted registry records lead to orphaned role trees, stale lock files, and race conditions during simultaneous provisioning. The workspace_registry_impl implementation component resolves role definitions dynamically from declarative role configuration files using TOML parsing (falling back to build files using AST evaluation when TOML is absent), normalizes role identifiers, computes directory hashes, and performs atomic JSON registry serialization with file locking.

**Out of scope:** The workspace_registry_impl implementation component does not provision directory contents, synchronize git state, or evaluate task dirty status; these are handled by other components.

## Types and Behavior

The workspace registry discovers the canonical repository root by ascending the directory tree until locating git metadata directories or canonical Bazel workspace indicators (ignoring projected role workspace directories containing `.cleanroom_role.json`), inspecting role metadata descriptors or matching sibling workspace conventions when called from within an isolated role workspace, and falling back to ambient process working directories when indicators are absent.

The workspace registry resolves role definitions by loading role definitions from declarative role configuration files (such as `cleanroom_python_roles.toml` in the repository root or methodology directory) using TOML parsing, or falling back to parsing define_role declarations from the repository's build file using AST evaluation when role configuration files are absent. It extracts all declared role attributes, derives writable file patterns from source patterns, derives read-only file patterns from role dependencies and star role dependencies, and computes audit tags for auditor roles without primary source artifacts. If a requested role is unknown or undeclared, role resolution fails fast and raises an explicit error without synthetic fallbacks.

The workspace registry computes role workspace directory paths by combining the repository root parent directory with the role name and directory scope, sanitizing directory delimiters into underscores to produce collision-free sibling workspaces.

The workspace registry reads and writes active workspace descriptors in the `.cleanroom_workspaces.json` registry file, performing atomic disk writes via temporary staging files to avoid concurrent read corruption. Registering a workspace appends or updates the descriptor in the registry, and unregistering removes matching workspace directories.
