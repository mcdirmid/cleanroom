<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: 0837040b5997
-->

# workspace_registry_impl implementation component

imports: agent_session
implements: workspace_registry

## Purpose

The workspace_registry_impl implementation component realizes role configuration resolution, path sanitization, and persistent workspace registration in `.cleanroom_workspaces.json`.

Reliable multi-role orchestration depends on atomic registry file updates and deterministic workspace naming conventions across platforms. Incomplete role resolution or corrupted registry records lead to orphaned role trees, stale lock files, and race conditions during simultaneous provisioning. The workspace_registry_impl implementation component resolves standard role templates (including high, planning, low, lib, test, qa, and coverage roles), normalizes role identifiers, computes directory hashes, and performs atomic JSON registry serialization with file locking.

**Out of scope:** The workspace_registry_impl implementation component does not provision directory contents, synchronize git state, or evaluate task dirty status; these are handled by other components.

## Types and Behavior

The workspace registry discovers the canonical repository root by ascending the directory tree until locating git metadata directories or canonical Bazel workspace indicators (ignoring projected role workspace directories containing `.cleanroom_role.json`), inspecting role metadata descriptors or matching sibling workspace conventions when called from within an isolated role workspace, and falling back to ambient process working directories when indicators are absent.

The workspace registry resolves role definitions by matching requested role names against standard Cleanroom roles or inspecting role rule targets. When matching standard roles, the registry provisions:

- The high role, granting write access to high-level markdown specifications and reading design guidelines.

- The planning role, granting write access to planning documents and reading upstream high-level specifications.

- The low role, granting write access to low-level Python stubs and reading planning documents and grounding stubs.

- The lib role, granting write access to library Python source files and reading low-level stubs and grounding specifications.

- The test role, granting write access to unit test source files and reading low-level stubs and library implementations.

- The qa role, performing logless verification audits over library implementations, unit tests, and contracts with the QA_AUDIT tag.

- The coverage role, verifying branch and statement execution thresholds with the COVERAGE_AUDIT tag.

The workspace registry computes role workspace directory paths by combining the repository root parent directory with the role name and directory scope, sanitizing directory delimiters into underscores to produce collision-free sibling workspaces.

The workspace registry reads and writes active workspace descriptors in the `.cleanroom_workspaces.json` registry file, performing atomic disk writes via temporary staging files to avoid concurrent read corruption. Registering a workspace appends or updates the descriptor in the registry, and unregistering removes matching workspace directories.
