<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-09T02:39:58Z
CHANGE: add contamination tripwire to AGENTS.md synthesis specification
CODE_HASH: 03216cce2696
-->

# workspace_provision_impl implementation component

imports: agent_session, workspace_registry
implements: workspace_provision

## Purpose

The workspace_provision_impl implementation component realizes role workspace filesystem initialization, permission-isolated copying, executable runner script deployment, and configuration synthesis.

Provisioning isolated role workspaces requires precise file-level permission control to prevent agent hallucinations from overwriting immutable upstream contracts or deleting build rules. Incomplete workspace preparation or dangling file handles can cause agent sessions to fail on startup or corrupt subsequent runs. The workspace_provision_impl implementation component creates directory trees, selectively copies source files and build configurations, applies read-only attributes to upstream dependencies, embeds self-contained zipapp runner wrappers in `bin/`, and writes `.cleanroom_role.json`.

**Out of scope:** The workspace_provision_impl implementation component does not parse git commits, evaluate forward dirty node propagation, or schedule multi-node builds; these are handled by other components.

**Delegated:** Role definition resolution, target directory computation, and workspace registry persistence are delegated to workspace_registry.

## Types and Behavior

The workspace provisioner commissions a role workspace at the resolved workspace directory path.

When commissioning a workspace, the provisioner:

- Validates that the target directory exists and resolves the role definition.

- Creates the role workspace working tree, copying workspace roots, project configurations, and build definitions while configuring type-checking to cover the workspace without directory exclusions.

- Inspects declared role patterns to identify writable target files, upstream contract dependencies, and stub role dependencies. For stub role dependencies, synthesizes read-only test stubs (`chmod 444`) with `raise NotImplementedError` from companion specifications (`low/*.pyi`) into the workspace, preventing implementation detail exposure to test author agents, while copying build definitions and package initializers.

- Copies writable target files into the workspace with standard write permissions (`chmod 644`), creating missing target skeletons when declared files do not yet exist on disk.

- Copies upstream contract dependencies and guides into the workspace with read-only permissions (`chmod 444`), ensuring agents cannot alter upstream specifications in-place.

- Deploys executable zipapp runner wrappers into the workspace `bin/` directory, packaging executable runners for `get_work`, `check_files`, `submit`, `blame`, `fail`, and `coverage` with execution permissions (`chmod 755`).

- Writes the `.cleanroom_role.json` configuration file recording role address, role name, directory scope, and canonical main repository root.

- Synthesizes `AGENTS.md` containing behavioral constraints, role instructions, strict boundary rules (workspace boundary, forbidding git operations, main repo read-only), a zero-tolerance contamination tripwire mandating immediate abort upon reading out-of-bounds files, an explicit fail-stop and reporting protocol (prohibiting self-healing on infrastructure tracebacks, errors, or missing dependencies while distinguishing ordinary verification test failures destined for blame attribution), and tool usage sequences tailored to the commissioned role.

- Registers the new workspace descriptor in the workspace registry.
