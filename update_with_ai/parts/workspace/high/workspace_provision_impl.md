<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: ef79d567f7bd
-->

# workspace_provision_impl implementation component

imports: agent_session, workspace_registry
implements: workspace_provision

## Purpose

The workspace_provision_impl implementation component realizes role workspace filesystem initialization, permission-isolated copying, executable runner script deployment, and workspace destruction.

Provisioning isolated role workspaces requires precise file-level permission control to prevent agent hallucinations from overwriting immutable upstream contracts or deleting build rules. Incomplete workspace preparation or dangling file handles can cause agent sessions to fail on startup or corrupt subsequent runs. The workspace_provision_impl implementation component creates directory trees, selectively copies source files and build configurations, applies read-only attributes to upstream dependencies, embeds self-contained zipapp runner wrappers in `bin/`, writes `.cleanroom_role.json`, and cleans up safely during decommissioning.

**Out of scope:** The workspace_provision_impl implementation component does not parse git commits, evaluate forward dirty node propagation, or schedule multi-node builds; these are handled by other components.

**Delegated:** Role definition resolution, target directory computation, and workspace registry persistence are delegated to workspace_registry.

## Types and Behavior

The workspace provisioner commissions a role workspace at the resolved workspace directory path.

When commissioning a workspace, the provisioner:

- Validates that the target directory exists and resolves the role definition.

- Creates the role workspace working tree, copying workspace roots and build definitions while pruning files outside the target directory scope.

- Inspects declared role patterns to identify writable target files and upstream contract dependencies.

- Copies writable target files into the workspace with standard write permissions (`chmod 644`), creating missing target skeletons when declared files do not yet exist on disk.

- Copies upstream contract dependencies and guides into the workspace with read-only permissions (`chmod 444`), ensuring agents cannot alter upstream specifications in-place.

- Deploys executable zipapp runner wrappers into the workspace `bin/` directory, packaging executable runners for `get_work`, `check_files`, `submit`, `blame`, `fail`, and `coverage` with execution permissions (`chmod 755`).

- Writes the `.cleanroom_role.json` configuration file recording role address, role name, directory scope, and canonical main repository root.

- Synthesizes `AGENTS.md` containing behavioral constraints, role instructions, strict boundary rules (workspace boundary, forbidding git operations, main repo read-only), an explicit fail-stop and reporting protocol (prohibiting self-healing on infrastructure tracebacks, errors, or missing dependencies), and tool usage sequences tailored to the commissioned role.

- Registers the new workspace descriptor in the workspace registry.

When decommissioning a workspace, the provisioner verifies whether any modified or unharvested files remain in the workspace. If modified files exist and force is not set, decommissioning fails with an error detailing pending work. When clean or forced, the provisioner unregisters the workspace and deletes the directory tree recursively.
