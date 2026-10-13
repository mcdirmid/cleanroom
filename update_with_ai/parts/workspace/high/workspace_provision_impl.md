<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-12T23:35:00Z
CHANGE: add command execution tripwire and impasse fail protocol to AGENTS.md synthesis specification
CODE_HASH: 11b11f74a16e
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# workspace_provision_impl implementation component

imports: agent_session, cleanroom_files_ext, workspace_registry
implements: workspace_provision

## Purpose

The workspace_provision_impl implementation component realizes role workspace filesystem initialization, permission-isolated copying, executable runner script deployment, and configuration synthesis.

Provisioning isolated role workspaces requires precise file-level permission control to prevent agent hallucinations from overwriting immutable upstream contracts or deleting build rules. Incomplete workspace preparation or dangling file handles can cause agent sessions to fail on startup or corrupt subsequent runs. The workspace_provision_impl implementation component creates directory trees, selectively copies source files and build configurations, applies read-only attributes to upstream dependencies, embeds self-contained zipapp runner wrappers in `bin/`, and writes the hidden role descriptor configuration file.

**Out of scope:** The workspace_provision_impl implementation component does not parse git commits, evaluate forward dirty node propagation, or schedule multi-node builds; these are handled by other components.

**Delegated:** Role definition resolution, target directory computation, and workspace registry persistence are delegated to workspace_registry. File naming conventions for the role descriptor configuration are delegated to cleanroom_files_ext.

## Types and Behavior

The workspace provisioner commissions a role workspace at the resolved workspace directory path.

The workspace provisioner:

- Validates that the target directory exists and resolves the role definition.

- Creates the role workspace working tree, copying workspace roots, project configurations, and build definitions while configuring type-checking to cover the workspace without directory exclusions.

- Inspects the declared role patterns to identify writable target files, upstream contract dependencies, and stub role dependencies.

- Synthesizes read-only test stubs raising `NotImplementedError` from the companion specification files into the workspace for stub role dependencies, preventing the exposure of implementation detail to test author agents, while copying build definitions and package initializers.

- Copies writable target files into the workspace with write permissions, creating a missing target skeleton when a declared file does not yet exist on disk.

- Copies upstream contract dependencies and guides into the workspace with read-only permissions, ensuring agents cannot alter an upstream specification in place.

- Deploys executable zipapp runner wrappers into the `bin/` directory of the workspace, packaging executable runners for the work, check files, submit, blame, fail, and coverage subcommands with execution permissions.

- Writes the role descriptor configuration file recording the role address, role name, directory scope, and canonical main repository root.

- Synthesizes an `AGENTS.md` guide containing the behavioral constraints, role instructions, and tool usage sequences tailored to the commissioned role.

- Writes boundary rules into the guide that confine the agent to the workspace, forbid git operations, and declare the main repository read-only, and writes a contamination tripwire that mandates an immediate abort upon reading an out-of-bounds file.

- Writes a command execution tripwire into the guide that strictly restricts execution to prescribed `bin/` executables (`bin/get_work`, `bin/check_files`, `bin/submit`, `bin/blame`, `bin/fail`) and mandates an immediate abort upon executing unapproved commands.

- Writes a fail-stop and reporting protocol into the guide that prohibits self-healing on an infrastructure traceback, error, or missing dependency, while distinguishing ordinary verification test failures and establishing an unresolvable impasse protocol where failures are recorded via `bin/fail` and escalated to the coordinator.

- Registers the new workspace descriptor in the workspace registry.
